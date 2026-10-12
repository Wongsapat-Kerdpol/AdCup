from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.submission import RejectedBy, SubmissionStatus


class AdminSubmissionRow(BaseModel):
    """One submission as an admin sees it in a campaign's submission list."""

    id: int
    campaign_id: int
    creator_id: int
    creator_name: str
    youtube_channel_id: str | None = None
    youtube_channel_title: str | None = None
    video_url: str
    external_video_id: str | None = None
    video_title: str | None = None
    status: SubmissionStatus
    submitted_at: datetime
    view_count: int
    gross_amount: Decimal
    net_amount: Decimal


class AdminSubmissionDetail(AdminSubmissionRow):
    """Everything about one submission — admins only (contains the creator's email)."""

    campaign_title: str
    creator_email: str
    creator_joined_at: datetime
    creator_submissions: int  # all submissions by this creator, every campaign
    creator_net_earned: Decimal  # net paid to this creator, every campaign
    video_channel_id: str | None = None
    video_published_at: datetime | None = None
    views_refreshed_at: datetime | None = None
    paid_views: int
    commission_amount: Decimal
    system_checked_at: datetime | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_by: RejectedBy | None = None
    rejection_reason: str | None = None
