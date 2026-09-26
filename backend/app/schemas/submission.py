"""[PERSON 2] Pydantic schemas for the submission lifecycle."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.submission import RejectedBy, SubmissionStatus


class SubmissionCreate(BaseModel):
    campaign_id: int
    video_url: str = Field(min_length=1, max_length=500)


class Submission(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    creator_id: int
    video_url: str
    platform: str
    external_video_id: str | None = None
    video_title: str | None = None
    video_channel_id: str | None = None
    video_published_at: datetime | None = None
    view_count: int
    views_refreshed_at: datetime | None = None

    status: SubmissionStatus
    system_checked_at: datetime | None = None
    reviewed_by_id: int | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_by: RejectedBy | None = None
    rejection_reason: str | None = None

    gross_amount: Decimal
    commission_amount: Decimal
    net_amount: Decimal
    paid_views: int

    created_at: datetime


class SubmissionForReview(Submission):
    """Everything the admin review queue needs, joined with campaign + creator info.

    Defaults let routers/review.py build this the same way RefreshResult is built in
    routers/youtube.py: model_validate(submission).model_copy(update={...}).
    """

    campaign_title: str = ""
    campaign_requirements: str = ""
    creator_name: str = ""


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
