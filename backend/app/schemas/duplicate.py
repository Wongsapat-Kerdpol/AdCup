from typing import Literal

from pydantic import BaseModel


class DuplicateMatch(BaseModel):
    submission_id: int
    campaign_title: str
    creator_name: str
    video_url: str
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
