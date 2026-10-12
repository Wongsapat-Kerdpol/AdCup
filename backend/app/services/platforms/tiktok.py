"""[PERSON 3] TikTok adapter — stats come from the creator's own token (ConnectedAccount)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connected_account import ConnectedAccount
from app.models.user import User
from app.services import tiktok as tt
from app.services.platforms.base import PlatformError, VideoStats

# Refresh a little before expiry so a call never goes out with a token that dies mid-request.
_EARLY_REFRESH = timedelta(minutes=5)


def linked_account(db: Session, creator: User) -> ConnectedAccount | None:
    return db.scalar(
        select(ConnectedAccount).where(ConnectedAccount.user_id == creator.id, ConnectedAccount.platform == "tiktok")
    )


def valid_access_token(db: Session, account: ConnectedAccount) -> str:
    """The account's access token, refreshed (and saved) first if it's about to expire."""
    now = datetime.now(timezone.utc)
    if account.access_expires_at and now < account.access_expires_at - _EARLY_REFRESH:
        return account.access_token
    if not account.refresh_token or (account.refresh_expires_at and now >= account.refresh_expires_at):
        raise PlatformError("Your TikTok login expired — reconnect TikTok in Settings")

    tokens = tt.refresh_access_token(account.refresh_token)
    account.access_token = tokens.access_token
    account.access_expires_at = tokens.access_expires_at
    if tokens.refresh_token:  # TikTok may rotate it; the old one stops working
        account.refresh_token = tokens.refresh_token
        account.refresh_expires_at = tokens.refresh_expires_at
    db.flush()
    return account.access_token


class TikTokAdapter:
    name = "tiktok"
    label = "TikTok"
    account_label = "TikTok account"
    stats_need_user_token = True

    def extract_video_id(self, url: str) -> str | None:
        return tt.extract_video_id(url)

    def connected_account_id(self, db: Session, creator: User) -> str | None:
        account = linked_account(db, creator)
        return account.account_id if account else None

    def connected_account_name(self, db: Session, creator: User) -> str | None:
        account = linked_account(db, creator)
        return account.username if account else None

    def fetch_video(self, db: Session, creator: User, video_id: str) -> VideoStats | None:
        account = linked_account(db, creator)
        if account is None:
            raise PlatformError("Connect your TikTok account in Settings first")

        video = tt.query_videos(valid_access_token(db, account), [video_id]).get(video_id)
        if video is None:  # not found, deleted, private — or simply not this creator's video
            return None
        return VideoStats(
            video_id=str(video["id"]),
            # video.query only returns the token owner's videos, so the owner is this account.
            owner_id=account.account_id,
            title=(video.get("title") or video.get("video_description") or "")[:300],
            published_at=datetime.fromtimestamp(int(video["create_time"]), tz=timezone.utc),
            view_count=int(video.get("view_count") or 0),
            is_public=True,  # the Display API only exposes public videos
        )
