"""[PERSON 3] Platform-agnostic endpoints: which platforms exist + views refresh for any of them.

  GET  /api/platforms                         — every platform, whether it's supported and whether the
                                                 current user has connected an account on it
  POST /api/platforms/refresh/{submission_id} — creator (owner) or admin: services.platforms.refresh_views()
                                                 (creators: at most once per REFRESH_COOLDOWN)
  POST /api/platforms/refresh-all             — admin: refresh every pending + approved submission,
                                                 then run one payout round (services/payout.py)
The old /api/youtube/refresh* paths still work (routers/youtube.py points them here).
Per-platform account linking lives in each platform's own router (youtube.py, ...).
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SUPPORTED_SUBMISSION_PLATFORMS
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.platform import PlatformStatus
from app.schemas.youtube import RefreshAllResult, RefreshResult
from app.services import platforms
from app.services.payout import settle_all

router = APIRouter(prefix="/api/platforms", tags=["platforms (Person 3)"])
log = logging.getLogger(__name__)

# Stops a creator from spamming the button (each refresh costs platform API quota).
REFRESH_COOLDOWN = timedelta(seconds=30)


@router.get("", response_model=list[PlatformStatus])
def list_platforms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = []
    for adapter in platforms.ADAPTERS.values():
        account_id = adapter.connected_account_id(db, user)
        result.append(
            PlatformStatus(
                name=adapter.name,
                label=adapter.label,
                account_label=adapter.account_label,
                supported=adapter.name in SUPPORTED_SUBMISSION_PLATFORMS,
                connected=account_id is not None,
                account_name=adapter.connected_account_name(db, user) if account_id else None,
            )
        )
    return result


@router.post("/refresh/{submission_id}", response_model=RefreshResult)
def refresh_submission(
    submission_id: int,
    user: User = Depends(require_role(UserRole.creator, UserRole.admin)),
    db: Session = Depends(get_db),
):
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if user.role == UserRole.creator and submission.creator_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your submission")
    if submission.status == SubmissionStatus.rejected:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Rejected submissions are not refreshed")

    last = submission.views_refreshed_at
    if user.role == UserRole.creator and last and datetime.now(timezone.utc) - last < REFRESH_COOLDOWN:
        return RefreshResult.model_validate(submission).model_copy(update={"throttled": True})

    adapter = platforms.get_adapter(submission.platform)
    label = adapter.label if adapter else submission.platform
    try:
        info = platforms.refresh_views(db, submission)
    except platforms.PlatformError as exc:  # e.g. the creator's TikTok login expired
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (httpx.HTTPError, RuntimeError) as exc:
        db.rollback()
        log.warning("refresh of submission %s failed: %s", submission_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not reach {label}, try again later")

    db.refresh(submission)
    return RefreshResult.model_validate(submission).model_copy(update={"video_found": info is not None})


@router.post("/refresh-all", response_model=RefreshAllResult)
def refresh_all(_: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    """Refresh every pending + approved video, then run ONE payout round so every video is judged on
    the same snapshot of views. One failure doesn't stop the batch."""
    pending = db.scalars(
        select(Submission).where(Submission.status == SubmissionStatus.pending).order_by(Submission.id)
    ).all()
    approved = db.scalars(
        select(Submission).where(Submission.status == SubmissionStatus.approved).order_by(Submission.id)
    ).all()

    result = RefreshAllResult(total=len(pending) + len(approved), refreshed=0, video_missing=0, failed=0)
    for submission in [*pending, *approved]:
        try:
            info = platforms.refresh_views(db, submission)
        except Exception as exc:  # keep going; one bad video or expired login mustn't block the rest
            db.rollback()
            log.warning("refresh-all: submission %s failed: %s", submission.id, exc)
            result.failed += 1
            continue
        result.refreshed += 1
        if info is None:
            result.video_missing += 1

    try:
        result.payouts = len(settle_all(db))
        db.commit()
    except Exception as exc:  # the views are already saved; the round can be re-run from /api/admin/payout-round
        db.rollback()
        log.warning("refresh-all: payout round failed: %s", exc)
    return result
