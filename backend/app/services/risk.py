"""Risk score from weak signals — docs/linked-account-detection-spec.md, section 6.3 (D3, D5, D7).

A device id or an IP never merges accounts: a family PC, a dorm's Wi-Fi or a mobile carrier's NAT is
shared by honest people. They only score a PAIR of accounts that are in different profile groups and
both submitted to the same campaign:

    same device                            +50   not counted if the device is used by > MAX_SHARE accounts
    same IP                                +10   +20 if one of them used it within 24 h of signing up;
                                                 not counted if the IP is used by > IP_HUB_SIZE accounts
    signed up within 10 minutes            +10
    submitted to the campaign within 1 h   +10

A pair scoring >= LINK_FLAG_SCORE gets a "suspected" flag. Their caps stay separate until an admin
confirms it (routers/linked_accounts.py); meanwhile both accounts' withdrawals are on hold.

Runs when a submission passes the system check (services/verification.py). Only flushes.
"""

from datetime import timedelta

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.core.config import IP_HUB_SIZE, LINK_FLAG_SCORE, MAX_SHARE
from app.models.identity import IdentitySignal, LinkFlag, LinkFlagKind, LinkFlagStatus, SignalType
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User

DEVICE_POINTS = 50
IP_POINTS = 10
IP_NEW_ACCOUNT_POINTS = 20
SIGNUP_POINTS = 10
SUBMIT_POINTS = 10
NEW_ACCOUNT_WINDOW = timedelta(hours=24)
SIGNUP_WINDOW = timedelta(minutes=10)
SUBMIT_WINDOW = timedelta(hours=1)

_HUB_SIZE = {SignalType.device_id: MAX_SHARE, SignalType.ip: IP_HUB_SIZE}
_WEAK = tuple(_HUB_SIZE)

Key = tuple[SignalType, str]


def _weak_signals(db: Session, user_id: int) -> dict[Key, IdentitySignal]:
    rows = db.scalars(
        select(IdentitySignal).where(IdentitySignal.user_id == user_id, IdentitySignal.type.in_(_WEAK))
    ).all()
    return {(s.type, s.value_hash): s for s in rows}


def _users_per_value(db: Session, keys: set[Key]) -> dict[Key, int]:
    if not keys:
        return {}
    rows = db.execute(
        select(IdentitySignal.type, IdentitySignal.value_hash, func.count(IdentitySignal.user_id.distinct()))
        .where(tuple_(IdentitySignal.type, IdentitySignal.value_hash).in_(list(keys)))
        .group_by(IdentitySignal.type, IdentitySignal.value_hash)
    ).all()
    return {(t, h): n for t, h, n in rows}


def _submitted_at(db: Session, user_id: int, campaign_id: int) -> list:
    return list(
        db.scalars(
            select(Submission.created_at).where(
                Submission.creator_id == user_id,
                Submission.campaign_id == campaign_id,
                Submission.status != SubmissionStatus.rejected,
            )
        ).all()
    )


def score_pair(db: Session, user: User, other: User, campaign_id: int) -> tuple[int, list[str]]:
    """Risk score of two accounts in a campaign, and which checks matched (in the order above)."""
    mine, theirs = _weak_signals(db, user.id), _weak_signals(db, other.id)
    shared = mine.keys() & theirs.keys()
    users_per_value = _users_per_value(db, shared)
    usable = {k for k in shared if users_per_value[k] <= _HUB_SIZE[k[0]]}  # spec D7: hubs count for nothing
    if not usable:
        return 0, []

    score, reasons = 0, []
    if any(t == SignalType.device_id for t, _ in usable):
        score += DEVICE_POINTS
        reasons.append("device_id")
    ips = [k for k in usable if k[0] == SignalType.ip]
    if ips:
        new_account = any(
            mine[k].first_seen_at - user.created_at <= NEW_ACCOUNT_WINDOW
            or theirs[k].first_seen_at - other.created_at <= NEW_ACCOUNT_WINDOW
            for k in ips
        )
        score += IP_NEW_ACCOUNT_POINTS if new_account else IP_POINTS
        reasons.append("ip")
    if abs(user.created_at - other.created_at) <= SIGNUP_WINDOW:
        score += SIGNUP_POINTS
        reasons.append("signup_time")
    other_times = _submitted_at(db, other.id, campaign_id)
    if any(abs(a - b) <= SUBMIT_WINDOW for a in _submitted_at(db, user.id, campaign_id) for b in other_times):
        score += SUBMIT_POINTS
        reasons.append("submit_time")
    return score, reasons


def _record_suspected(db: Session, user_id: int, other_id: int, campaign_id: int, score: int, reasons: list[str]):
    a, b = sorted((user_id, other_id))
    previous = db.scalars(
        select(LinkFlag).where(
            LinkFlag.kind == LinkFlagKind.suspected, LinkFlag.user_a_id == a, LinkFlag.user_b_id == b
        )
    ).all()
    for flag in previous:
        if flag.status == LinkFlagStatus.open:
            if score > (flag.score or 0):
                flag.score, flag.reasons = score, reasons
            return None
        if flag.status == LinkFlagStatus.confirmed:
            return None
        if flag.status == LinkFlagStatus.dismissed and set(reasons) <= set(flag.reasons):
            return None  # an admin already said "different people" on this evidence
    flag = LinkFlag(
        kind=LinkFlagKind.suspected, user_a_id=a, user_b_id=b, campaign_id=campaign_id, score=score, reasons=reasons
    )
    db.add(flag)
    return flag


def flag_suspected_links(db: Session, submission: Submission) -> list[LinkFlag]:
    """Score the submitter against every account that shares a device or IP with them and also submitted
    to this campaign from another profile group. Returns the new "suspected" flags."""
    user = db.get(User, submission.creator_id)
    mine = _weak_signals(db, user.id)
    if not mine:
        return []
    sharing = (
        select(IdentitySignal.user_id)
        .where(
            tuple_(IdentitySignal.type, IdentitySignal.value_hash).in_(list(mine)),
            IdentitySignal.user_id != user.id,
        )
        .distinct()
    )
    in_campaign = select(Submission.creator_id).where(
        Submission.campaign_id == submission.campaign_id, Submission.status != SubmissionStatus.rejected
    )
    others = db.scalars(select(User).where(User.id.in_(sharing), User.id.in_(in_campaign)).order_by(User.id)).all()

    my_group = user.profile_group_id or user.id
    flags = []
    for other in others:
        if (other.profile_group_id or other.id) == my_group:
            continue  # already one profile: nothing to flag
        score, reasons = score_pair(db, user, other, submission.campaign_id)
        if score >= LINK_FLAG_SCORE:
            flag = _record_suspected(db, user.id, other.id, submission.campaign_id, score, reasons)
            if flag is not None:
                flags.append(flag)
    db.flush()
    return flags
