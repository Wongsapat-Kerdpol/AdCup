"""[PERSON 3] YouTube adapter — wraps services/youtube.py (API key stats, OAuth channel on User)."""

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import youtube as yt
from app.services.platforms.base import VideoStats


class YouTubeAdapter:
    name = "youtube"
    label = "YouTube"
    account_label = "YouTube channel"
    stats_need_user_token = False

    def extract_video_id(self, url: str) -> str | None:
        return yt.extract_video_id(url)

    def connected_account_id(self, db: Session, creator: User) -> str | None:
        return creator.youtube_channel_id

    def connected_account_name(self, db: Session, creator: User) -> str | None:
        return creator.youtube_channel_title

    def fetch_video(self, db: Session, creator: User, video_id: str) -> VideoStats | None:
        # Looked up on the module at call time so tests can monkeypatch services.youtube.get_video_info.
        info = yt.get_video_info(video_id)
        if info is None:
            return None
        return VideoStats(
            video_id=info.video_id,
            owner_id=info.channel_id,
            title=info.title,
            published_at=info.published_at,
            view_count=info.view_count,
            is_public=info.is_public,
        )
