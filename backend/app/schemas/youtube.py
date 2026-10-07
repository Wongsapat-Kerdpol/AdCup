from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.submission import SubmissionStatus


class ConnectResponse(BaseModel):
    """The frontend sends the browser here (a plain redirect can't carry the JWT header)."""

    auth_url: str


class RefreshResult(BaseModel):
    """One submission after a views refresh (and Person 2's check / payout, if it ran)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: SubmissionStatus
    video_title: str | None = None
    view_count: int
    paid_views: int
    views_refreshed_at: datetime | None = None
    video_found: bool = True  # False: the video is gone or private on YouTube
    throttled: bool = False  # True: refreshed too recently, returned the stored numbers


class RefreshAllResult(BaseModel):
    total: int
    refreshed: int
    video_missing: int
    failed: int
    payouts: int = 0  # payments made by the payout round that follows the refresh
