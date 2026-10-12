"""[PERSON 3] What every video platform adapter provides.

The system check, submission intake and views refresh only talk to this interface, so adding a
platform means writing one adapter and registering it in services/platforms/__init__.py.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.models.user import User


class PlatformError(RuntimeError):
    """The platform can't answer right now for this creator (not connected, token revoked/expired).
    Subclass of RuntimeError so existing `except (httpx.HTTPError, RuntimeError)` handlers cover it."""


@dataclass
class VideoStats:
    video_id: str
    owner_id: str  # channel / account id on the platform; compared with the creator's linked account
    title: str
    published_at: datetime
    view_count: int
    is_public: bool


class PlatformAdapter(Protocol):
    name: str  # stored in Submission.platform / Campaign.platforms, e.g. "youtube"
    label: str  # "YouTube"
    account_label: str  # "YouTube channel" — used in messages like "Connect your YouTube channel"
    # True when stats can only be read with the creator's own OAuth token (TikTok).
    # False when a server-side API key is enough (YouTube).
    stats_need_user_token: bool

    def extract_video_id(self, url: str) -> str | None:
        """Video id if the URL belongs to this platform, else None."""

    def connected_account_id(self, db: Session, creator: User) -> str | None:
        """The creator's linked account id on this platform, or None if not connected."""

    def connected_account_name(self, db: Session, creator: User) -> str | None:
        """Human-readable name of that account (channel title / @username), for display."""

    def fetch_video(self, db: Session, creator: User, video_id: str) -> VideoStats | None:
        """Fresh stats, or None if the video doesn't exist / isn't visible.
        Raises httpx.HTTPError on outages and PlatformError on account problems."""
