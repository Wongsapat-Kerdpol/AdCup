"""[PERSON 3] Google OAuth + YouTube view refresh.

  GET  /api/youtube/connect                 — creator: returns the Google consent URL
                                               (scope: openid youtube.readonly).
                                               JSON instead of a 302 because the browser can't attach
                                               the JWT to a plain navigation; the frontend redirects.
  GET  /api/youtube/callback                — Google redirects here: exchange code, record the Google account id
                                               (linked account detection), channels.list?mine=true,
                                               save User.youtube_channel_id / _title / google_refresh_token
                                               (never returned to the frontend), then redirect to /settings
  POST /api/youtube/disconnect              — revoke the token at Google and clear those fields
  POST /api/youtube/refresh/{submission_id} — creator (owner) or admin: services.youtube.refresh_views()
                                               (creators: at most once per REFRESH_COOLDOWN)
  POST /api/youtube/refresh-all             — admin: refresh every pending + approved submission,
                                               then run one payout round (services/payout.py)
Config: settings.google_client_id / google_client_secret / google_redirect_uri
Google Cloud: enable "YouTube Data API v3", OAuth consent screen in Testing mode, add the team's
emails as test users (tokens of Testing-mode apps expire after 7 days — reconnect if needed).
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.models.identity import SignalType
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.user import UserPublic
from app.schemas.youtube import ConnectResponse, RefreshAllResult, RefreshResult
from app.services import youtube as yt
from app.services.identity import record_signal
from app.services.linking import rebuild_profile_groups
from app.services.payout import settle_all

router = APIRouter(prefix="/api/youtube", tags=["youtube (Person 3)"])
log = logging.getLogger(__name__)

_STATE_PURPOSE = "youtube_connect"
_STATE_TTL = timedelta(minutes=10)
# Stops a creator from spamming the button (each refresh costs YouTube API quota).
REFRESH_COOLDOWN = timedelta(seconds=30)


def _settings_redirect(result: str) -> RedirectResponse:
    """Back to the frontend's /settings page; it shows a toast for ?youtube=<result>."""
    frontend = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    return RedirectResponse(f"{frontend}/settings?{urlencode({'youtube': result})}")


@router.get("/connect", response_model=ConnectResponse)
def connect(user: User = Depends(require_role(UserRole.creator))):
    if not yt.oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube connect is not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)",
        )
    # Signed, short-lived state: tells the callback which user started the flow and blocks forged callbacks.
    state = jwt.encode(
        {"sub": str(user.id), "purpose": _STATE_PURPOSE, "exp": datetime.now(timezone.utc) + _STATE_TTL},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return ConnectResponse(auth_url=yt.build_auth_url(state))


@router.get("/callback", include_in_schema=False)
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:  # e.g. the user pressed Cancel on Google's consent screen
        return _settings_redirect("denied")
    if not code or not state:
        return _settings_redirect("error")

    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != _STATE_PURPOSE:
            raise jwt.InvalidTokenError("wrong purpose")
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return _settings_redirect("expired")
    if user is None or user.role != UserRole.creator:
        return _settings_redirect("error")

    try:
        tokens = yt.exchange_code(code)
    except httpx.HTTPError:
        return _settings_redirect("error")

    # Linked account detection: recorded even when the channel is missing or taken below — signing in
    # to the Google account that owns another account's channel proves it is the same person.
    google_sub = yt.google_sub_from(tokens)
    if google_sub and record_signal(db, user, SignalType.google_sub, google_sub):
        rebuild_profile_groups(db)
        db.commit()

    # Google lets the user untick scopes on the consent screen; without YouTube we can't see the channel.
    if not yt.has_youtube_scope(tokens):
        return _settings_redirect("missing_scope")
    try:
        channel = yt.get_my_channel(tokens["access_token"])
    except (httpx.HTTPError, KeyError):
        return _settings_redirect("error")

    if channel is None:
        return _settings_redirect("no_channel")

    # One channel -> one AdCup account, otherwise two accounts could claim the same videos.
    owner = db.scalar(select(User).where(User.youtube_channel_id == channel.channel_id, User.id != user.id))
    if owner is not None:
        return _settings_redirect("channel_taken")

    user.youtube_channel_id = channel.channel_id
    user.youtube_channel_title = channel.title
    if tokens.get("refresh_token"):
        user.google_refresh_token = tokens["refresh_token"]
    db.commit()
    return _settings_redirect("connected")


@router.post("/disconnect", response_model=UserPublic)
def disconnect(user: User = Depends(require_role(UserRole.creator)), db: Session = Depends(get_db)):
    if user.google_refresh_token:
        yt.revoke_token(user.google_refresh_token)
    user.youtube_channel_id = None
    user.youtube_channel_title = None
    user.google_refresh_token = None
    db.commit()
    db.refresh(user)
    return user


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

    try:
        info = yt.refresh_views(db, submission)
    except (httpx.HTTPError, RuntimeError) as exc:
        db.rollback()
        log.warning("refresh of submission %s failed: %s", submission_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach YouTube, try again later")

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
        select(Submission)
        .where(Submission.status == SubmissionStatus.approved)
        .order_by(Submission.id)
    ).all()

    result = RefreshAllResult(total=len(pending) + len(approved), refreshed=0, video_missing=0, failed=0)
    for submission in [*pending, *approved]:
        try:
            info = yt.refresh_views(db, submission)
        except Exception as exc:  # keep going; one bad video or Person 2 error mustn't block the rest
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
