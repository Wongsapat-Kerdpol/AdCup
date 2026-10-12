from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.submission import SubmissionStatus


class DuplicateMatch(BaseModel):
    submission_id: int
    campaign_id: int
    campaign_title: str
    creator_name: str
    video_url: str
    status: SubmissionStatus
    submitted_at: datetime
    net_paid: Decimal
    submitted_earlier: bool  # true -> sent before the clip being reviewed, most likely the original
    days_apart: float
    matched_pictures: int
    total_pictures: int
    similarity: float
    closest_distance: int
    mirrored: bool
    level: Literal["copy", "check"]


class DuplicateReport(BaseModel):
    enabled: bool = True
    status: Literal["ok", "no_pictures", "unavailable", "disabled"]
    pictures_checked: int = 0
    level: Literal["copy", "check"] | None = None
    matches: list[DuplicateMatch] = []
    comparisons: int = 0
    linear_comparisons: int = 0


class DuplicateIndexStats(BaseModel):
    fingerprints: int
    submissions: int
