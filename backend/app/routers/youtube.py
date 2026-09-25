"""[PERSON 3] Google OAuth + YouTube view refresh.

  GET  /api/youtube/connect                 — creator: returns the Google consent URL (scope: youtube.readonly).
                                               JSON instead of a 302 because the browser can't attach
                                               the JWT to a plain navigation; the frontend redirects.
  GET  /api/youtube/callback                — Google redirects here: exchange code, channels.list?mine=true,
                                               save User.youtube_channel_id / _title / google_refresh_token
                                               (never returned to the frontend), then redirect to /settings
  POST /api/youtube/disconnect              — revoke the token at Google and clear those fields
TODO(Person 3):
  POST /api/youtube/refresh/{submission_id} — creator (owner) or admin: services.youtube.refresh_views()
  POST /api/youtube/refresh-all             — admin: refresh every pending + approved submission
                                               (approved ones in approved_at order -> FCFS payouts)
Config: settings.google_client_id / google_client_secret / google_redirect_uri
Google Cloud: enable "YouTube Data API v3", OAuth consent screen in Testing mode, add the team's
emails as test users (tokens of Testing-mode apps expire after 7 days — reconnect if needed).
"""

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
from app.models.user import User, UserRole
from app.schemas.user import UserPublic
from app.schemas.youtube import ConnectResponse
from app.services import youtube as yt

router = APIRouter(prefix="/api/youtube", tags=["youtube (Person 3)"])

_STATE_PURPOSE = "youtube_connect"
_STATE_TTL = timedelta(minutes=10)


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
