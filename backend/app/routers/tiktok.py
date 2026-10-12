"""[PERSON 3] TikTok account linking (Login Kit). Views refresh is shared: routers/platforms.py.

  GET  /api/tiktok/connect    — creator: returns the TikTok consent URL (scopes user.info.basic, video.list)
  GET  /api/tiktok/callback   — TikTok redirects here: exchange code, read open_id + display name,
                                 save a ConnectedAccount (tokens never sent to the frontend),
                                 then redirect to /settings?tiktok=<result>
  POST /api/tiktok/disconnect — revoke at TikTok (best effort) and delete the ConnectedAccount
Config: TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REDIRECT_URI (must be https — ngrok in dev).
TikTok app in Sandbox mode: only its target users can log in.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.connected_account import ConnectedAccount
from app.models.user import User, UserRole
from app.schemas.youtube import ConnectResponse
from app.services import tiktok as tt
from app.services.platforms.oauth import make_state, read_state, settings_redirect
from app.services.platforms.tiktok import linked_account

router = APIRouter(prefix="/api/tiktok", tags=["tiktok (Person 3)"])
PLATFORM = "tiktok"


@router.get("/connect", response_model=ConnectResponse)
def connect(user: User = Depends(require_role(UserRole.creator))):
    if not tt.oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TikTok connect is not configured (TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REDIRECT_URI)",
        )
    return ConnectResponse(auth_url=tt.build_auth_url(make_state(user.id, PLATFORM)))


@router.get("/callback", include_in_schema=False)
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:  # e.g. the user pressed Cancel on TikTok's consent screen
        return settings_redirect(PLATFORM, "denied")
    if not code or not state:
        return settings_redirect(PLATFORM, "error")

    user_id = read_state(state, PLATFORM)
    if user_id is None:
        return settings_redirect(PLATFORM, "expired")
    user = db.get(User, user_id)
    if user is None or user.role != UserRole.creator:
        return settings_redirect(PLATFORM, "error")

    try:
        tokens = tt.exchange_code(code)
        profile = tt.get_user(tokens.access_token)
    except (httpx.HTTPError, tt.TikTokAuthError, KeyError):
        return settings_redirect(PLATFORM, "error")

    taken = db.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.platform == PLATFORM,
            ConnectedAccount.account_id == profile.open_id,
            ConnectedAccount.user_id != user.id,
        )
    )
    if taken is not None:
        return settings_redirect(PLATFORM, "account_taken")

    account = linked_account(db, user) or ConnectedAccount(user_id=user.id, platform=PLATFORM)
    account.account_id = profile.open_id
    account.username = profile.display_name
    account.access_token = tokens.access_token
    account.access_expires_at = tokens.access_expires_at
    account.refresh_token = tokens.refresh_token
    account.refresh_expires_at = tokens.refresh_expires_at
    db.add(account)
    db.commit()
    return settings_redirect(PLATFORM, "connected")


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(user: User = Depends(require_role(UserRole.creator)), db: Session = Depends(get_db)):
    account = linked_account(db, user)
    if account is not None:
        tt.revoke(account.access_token)
        db.delete(account)
        db.commit()
