"""[PERSON 3] Registry of video platforms + the platform-agnostic views refresh.

    detect(url)                 -> (adapter, video_id) | None   which platform a pasted link is from
    get_adapter(name)           -> adapter | None
    refresh_views(db, submission) -> VideoStats | None          fresh stats, then the system check

A platform is accepted for submissions only if it is registered here AND listed in
config.SUPPORTED_SUBMISSION_PLATFORMS.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import SUPPORTED_SUBMISSION_PLATFORMS
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.services.platforms.base import PlatformAdapter, PlatformError, VideoStats
from app.services.platforms.youtube import YouTubeAdapter

__all__ = ["PlatformAdapter", "PlatformError", "VideoStats", "ADAPTERS", "get_adapter", "detect", "refresh_views"]

ADAPTERS: dict[str, PlatformAdapter] = {a.name: a for a in (YouTubeAdapter(),)}


def get_adapter(name: str) -> PlatformAdapter | None:
    return ADAPTERS.get(name)


def supported_adapters() -> list[PlatformAdapter]:
    return [a for name, a in ADAPTERS.items() if name in SUPPORTED_SUBMISSION_PLATFORMS]


def detect(url: str) -> tuple[PlatformAdapter, str] | None:
    """Which registered platform a link belongs to, with its video id."""
    for adapter in ADAPTERS.values():
        video_id = adapter.extract_video_id(url)
        if video_id:
            return adapter, video_id
    return None


def refresh_views(db: Session, submission: Submission) -> VideoStats | None:
    """Pull fresh stats onto the submission; a pending one then goes through the system check.

    Approved videos are only paid in payout rounds (services/payout.py), so refreshing more often
    gives no advantage. Returns None when the video is gone / not visible (stored stats are kept).
    Raises httpx.HTTPError / RuntimeError (incl. PlatformError) without saving anything.
    """
    adapter = get_adapter(submission.platform)
    if adapter is None:
        raise PlatformError(f"Platform '{submission.platform}' is not supported")
    creator = db.get(User, submission.creator_id)

    video_id = submission.external_video_id or adapter.extract_video_id(submission.video_url)
    stats = adapter.fetch_video(db, creator, video_id) if video_id else None

    submission.views_refreshed_at = datetime.now(timezone.utc)
    if stats is not None:
        submission.external_video_id = stats.video_id
        submission.video_title = stats.title[:300]
        submission.video_channel_id = stats.owner_id
        submission.video_published_at = stats.published_at
        submission.view_count = stats.view_count
    db.flush()

    if submission.status == SubmissionStatus.pending:
        from app.services.verification import run_system_check  # verification imports this module

        run_system_check(db, submission)

    db.commit()
    return stats
