"""[ANTI-FRAUD] Duplicate-clip checker: warns admins when a submission looks like a re-upload.

  pictures  : YouTube's cover (hqdefault.jpg) + its 3 auto frames (1.jpg, 2.jpg, 3.jpg)
  INSERT    : each usable picture -> dHash (64 bits) -> stored in video_hashes + the BK-Tree
  SEARCH    : every picture of the new clip is looked up in the BK-Tree (radius 8 bits), also
              flipped left-right to catch mirrored copies
  COUNT     : per old clip, how many of the new clip's pictures matched -> similarity %
  SORT      : merge sort, most suspicious first
  DELETE    : a rejected submission is removed from the tree (lazy delete)

Warnings (the admin always makes the final call):
  red    "Probably a copy" : similarity >= DUPLICATE_COPY_RATIO (60%)
  yellow "Should check"    : below that, but at least one picture within DUPLICATE_NEAR_EXACT (3 bits)

Plain black/white pictures are skipped, and a creator's own clips are never compared with each other.
Hashes are computed on demand (when an admin opens the review queue), so no other module calls this.
"""

import io
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import httpx
from PIL import Image
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.algorithms.bktree import BKTree
from app.algorithms.dhash import dhash, dhash_mirrored, is_flat
from app.algorithms.sorting import merge_sort
from app.core.config import DUPLICATE_COPY_RATIO, DUPLICATE_MATCH_RADIUS, DUPLICATE_NEAR_EXACT
from app.models.campaign import Campaign
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.models.video_hash import VideoHash

FRAMES = ("hqdefault", "1", "2", "3")
THUMB_URL = "https://i.ytimg.com/vi/{video_id}/{frame}.jpg"
BACKFILL_LIMIT = 50  # max older submissions hashed per request (each needs up to 4 small downloads)

FrameFetcher = Callable[[str], list[tuple[str, Image.Image]]]

_U64 = 1 << 64


def to_signed(h: int) -> int:
    """Unsigned 64-bit hash -> value that fits a Postgres BIGINT."""
    return h - _U64 if h >= 1 << 63 else h


def to_unsigned(v: int) -> int:
    return v + _U64 if v < 0 else v


def fetch_youtube_frames(video_id: str) -> list[tuple[str, Image.Image]]:
    """Download the cover + 3 auto frames. Missing pictures (404) are skipped.
    Raises httpx.HTTPError if YouTube can't be reached."""
    frames = []
    with httpx.Client(timeout=10) as client:
        for frame in FRAMES:
            resp = client.get(THUMB_URL.format(video_id=video_id, frame=frame))
            if resp.status_code != 200:
                continue
            try:
                img = Image.open(io.BytesIO(resp.content))
                img.load()
            except Exception:  # not a picture
                continue
            frames.append((frame, img))
    return frames


# --- In-memory index -------------------------------------------------------------------------


class DuplicateIndex:
    """BK-Tree of every fingerprint, plus who owns each submission (to skip a creator's own clips)."""

    def __init__(self) -> None:
        self.tree = BKTree()
        self.creator_of: dict[int, int] = {}
        self.loaded = False
        self.lock = threading.Lock()

    def add(self, submission_id: int, creator_id: int, hashes: list[int]) -> None:
        for h in hashes:
            self.tree.insert(h, submission_id)
        self.creator_of[submission_id] = creator_id

    def remove(self, submission_id: int) -> None:
        self.tree.delete_owner(submission_id)
        self.creator_of.pop(submission_id, None)

    def load(self, db: Session) -> None:
        rows = db.execute(
            select(VideoHash.submission_id, VideoHash.value, Submission.creator_id)
            .join(Submission, Submission.id == VideoHash.submission_id)
            .where(Submission.status != SubmissionStatus.rejected)
            .order_by(VideoHash.id)
        ).all()
        for submission_id, value, creator_id in rows:
            self.add(submission_id, creator_id, [to_unsigned(value)])
        self.loaded = True


_index = DuplicateIndex()


def get_index(db: Session) -> DuplicateIndex:
    if not _index.loaded:
        _index.load(db)
    return _index


@event.listens_for(Submission.status, "set")
def _forget_rejected(target: Submission, value, _old, _initiator) -> None:
    """DELETE: as soon as a submission is rejected, it stops showing up as a possible original."""
    if value == SubmissionStatus.rejected and target.id is not None and _index.loaded:
        _index.remove(target.id)


# --- Hashing ---------------------------------------------------------------------------------


@dataclass
class _Fingerprints:
    normal: list[int] = field(default_factory=list)
    mirrored: list[int] = field(default_factory=list)


def ensure_hashes(db: Session, submission: Submission, index: DuplicateIndex, fetch: FrameFetcher) -> _Fingerprints:
    """Stored fingerprints of a submission; computes + stores + INSERTs them the first time."""
    rows = db.scalars(select(VideoHash).where(VideoHash.submission_id == submission.id).order_by(VideoHash.id)).all()
    if rows:
        return _Fingerprints([to_unsigned(r.value) for r in rows], [to_unsigned(r.mirrored_value) for r in rows])
    if submission.platform != "youtube" or not submission.external_video_id:
        return _Fingerprints()

    prints = _Fingerprints()
    for frame, img in fetch(submission.external_video_id):
        if is_flat(img):
            continue
        h = dhash(img)
        if h in prints.normal:  # the cover is often one of the auto frames
            continue
        m = dhash_mirrored(img)
        prints.normal.append(h)
        prints.mirrored.append(m)
        db.add(VideoHash(submission_id=submission.id, frame=frame, value=to_signed(h), mirrored_value=to_signed(m)))
    db.flush()
    if prints.normal and submission.status != SubmissionStatus.rejected:
        index.add(submission.id, submission.creator_id, prints.normal)
    return prints


def backfill(db: Session, index: DuplicateIndex, fetch: FrameFetcher, limit: int = BACKFILL_LIMIT) -> int:
    """Hash older submissions that were never checked, so they can be found as originals."""
    missing = db.scalars(
        select(Submission)
        .where(
            Submission.status != SubmissionStatus.rejected,
            Submission.external_video_id.is_not(None),
            ~select(VideoHash.id).where(VideoHash.submission_id == Submission.id).exists(),
        )
        .order_by(Submission.id)
        .limit(limit)
    ).all()
    for submission in missing:
        ensure_hashes(db, submission, index, fetch)
    return len(missing)


# --- Report ----------------------------------------------------------------------------------


@dataclass
class Match:
    submission_id: int
    campaign_id: int
    campaign_title: str
    creator_name: str
    video_url: str
    status: str  # the other clip's review status
    submitted_at: datetime
    net_paid: Decimal  # what the other clip has already earned
    submitted_earlier: bool  # sent before this clip -> most likely the original
    days_apart: float  # |difference| between the two submission times, in days
    matched_pictures: int
    total_pictures: int
    similarity: float  # 0..1
    closest_distance: int  # smallest Hamming distance of any matching picture
    mirrored: bool  # the closest match was found with the flipped picture
    level: str  # "copy" (red) | "check" (yellow)


@dataclass
class Report:
    status: str  # "ok" | "no_pictures"
    pictures_checked: int
    level: str | None  # worst warning across matches: "copy" | "check" | None
    matches: list[Match]
    comparisons: int  # Hamming distances computed by the BK-Tree for this check
    linear_comparisons: int  # what checking every stored fingerprint would have cost


def check_submission(
    db: Session,
    submission: Submission,
    index: DuplicateIndex | None = None,
    fetch: FrameFetcher = fetch_youtube_frames,
) -> Report:
    index = index or get_index(db)
    with index.lock:
        backfill(db, index, fetch)
        prints = ensure_hashes(db, submission, index, fetch)
        if not prints.normal:
            return Report("no_pictures", 0, None, [], 0, 0)

        # SEARCH + COUNT
        found: dict[int, dict] = {}  # old submission id -> {"pictures": set, "closest": int, "mirrored": bool}
        before = index.tree.comparisons
        for i, (h, m) in enumerate(zip(prints.normal, prints.mirrored)):
            for query, mirrored in ((h, False), (m, True)):
                for owner, distance in index.tree.search(query, DUPLICATE_MATCH_RADIUS):
                    if owner == submission.id or index.creator_of.get(owner) == submission.creator_id:
                        continue
                    hit = found.setdefault(owner, {"pictures": set(), "closest": 65, "mirrored": False})
                    hit["pictures"].add(i)  # one picture counts once per old clip
                    if distance < hit["closest"]:
                        hit["closest"], hit["mirrored"] = distance, mirrored
        comparisons = index.tree.comparisons - before
        linear = index.tree.size * len(prints.normal) * 2

    total = len(prints.normal)
    flagged = {}
    for owner, hit in found.items():
        similarity = len(hit["pictures"]) / total
        if similarity >= DUPLICATE_COPY_RATIO:
            flagged[owner] = (hit, similarity, "copy")
        elif hit["closest"] <= DUPLICATE_NEAR_EXACT:
            flagged[owner] = (hit, similarity, "check")

    details = {}
    if flagged:
        rows = db.execute(
            select(
                Submission.id,
                Submission.video_url,
                Submission.campaign_id,
                Submission.status,
                Submission.created_at,
                Submission.net_amount,
                Campaign.title,
                User.display_name,
            )
            .join(Campaign, Campaign.id == Submission.campaign_id)
            .join(User, User.id == Submission.creator_id)
            .where(Submission.id.in_(list(flagged)), Submission.status != SubmissionStatus.rejected)
        ).all()
        details = {r.id: r for r in rows}

    def _apart(other_id: int, other_at: datetime) -> tuple[bool, float]:
        """(was the other clip sent first?, days between the two). Same time -> lower id came first."""
        earlier = (other_at, other_id) < (submission.created_at, submission.id)
        return earlier, round(abs((submission.created_at - other_at).total_seconds()) / 86400, 1)

    matches = [
        Match(
            submission_id=owner,
            campaign_id=details[owner].campaign_id,
            campaign_title=details[owner].title,
            creator_name=details[owner].display_name,
            video_url=details[owner].video_url,
            status=details[owner].status.value,
            submitted_at=details[owner].created_at,
            net_paid=details[owner].net_amount,
            submitted_earlier=_apart(owner, details[owner].created_at)[0],
            days_apart=_apart(owner, details[owner].created_at)[1],
            matched_pictures=len(hit["pictures"]),
            total_pictures=total,
            similarity=round(similarity, 3),
            closest_distance=hit["closest"],
            mirrored=hit["mirrored"],
            level=level,
        )
        for owner, (hit, similarity, level) in flagged.items()
        if owner in details
    ]
    # SORT: red before yellow, then most similar, then closest picture, then sent earlier (the likely original)
    matches = merge_sort(
        matches,
        key=lambda x: (x.level == "copy", x.similarity, -x.closest_distance, x.submitted_earlier),
        descending=True,
    )
    level = "copy" if any(m.level == "copy" for m in matches) else ("check" if matches else None)
    return Report("ok", total, level, matches, comparisons, linear)


def index_stats(db: Session) -> dict:
    index = get_index(db)
    return {
        "fingerprints": index.tree.size,
        "submissions": len(index.creator_of),
    }
