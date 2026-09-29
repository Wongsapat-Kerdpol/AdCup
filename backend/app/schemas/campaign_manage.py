"""[PERSON 1] Request/response schemas for brand campaign management (routers/campaign_manage.py)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import DEFAULT_MIN_VIEWS, SUPPORTED_SUBMISSION_PLATFORMS
from app.models.campaign import CampaignCategory, CampaignStatus, Platform
from app.models.submission import SubmissionStatus
from app.schemas.campaign import CampaignDetail

# Upper bounds keep values inside the Numeric(12,2) / Numeric(14,2) columns.
MAX_RATE = Decimal("100000")
MAX_BUDGET = Decimal("100000000")


class CampaignCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    # What the admin checks in round 2, e.g. "the water bottle must be visible".
    requirements: str = Field(min_length=10, max_length=5000)
    category: CampaignCategory
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.youtube], min_length=1)
    thumbnail_url: str | None = Field(None, max_length=500)

    rate_per_1k_views: Decimal = Field(gt=0, le=MAX_RATE, decimal_places=2)
    total_budget: Decimal = Field(gt=0, le=MAX_BUDGET, decimal_places=2)
    cap_per_post: Decimal | None = Field(None, gt=0, le=MAX_BUDGET, decimal_places=2)
    cap_per_profile: Decimal | None = Field(None, gt=0, le=MAX_BUDGET, decimal_places=2)
    min_views: int = Field(DEFAULT_MIN_VIEWS, ge=0, le=100_000_000)
    deadline: datetime | None = None

    @field_validator("title", "description", "requirements", mode="before")
    @classmethod
    def strip_text(cls, v):
        # Runs before the length checks, so "   " counts as empty.
        return v.strip() if isinstance(v, str) else v

    @field_validator("thumbnail_url")
    @classmethod
    def check_thumbnail(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("Thumbnail must be an http(s) image URL")
        return v

    @field_validator("platforms")
    @classmethod
    def check_platforms(cls, v: list[Platform]) -> list[Platform]:
        unsupported = [p.value for p in v if p.value not in SUPPORTED_SUBMISSION_PLATFORMS]
        if unsupported:
            raise ValueError(f"Not supported yet: {', '.join(unsupported)}")
        return list(dict.fromkeys(v))  # drop duplicates, keep order

    @field_validator("deadline")
    @classmethod
    def deadline_has_timezone(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("Deadline must include a timezone")
        return v

    @model_validator(mode="after")
    def check_caps(self):
        if self.cap_per_post is not None and self.cap_per_post > self.total_budget:
            raise ValueError("Cap per post can't be more than the total budget")
        if self.cap_per_profile is not None and self.cap_per_profile > self.total_budget:
            raise ValueError("Cap per creator can't be more than the total budget")
        if (
            self.cap_per_post is not None
            and self.cap_per_profile is not None
            and self.cap_per_post > self.cap_per_profile
        ):
            raise ValueError("Cap per post can't be more than the cap per creator")
        return self


class CampaignUpdate(BaseModel):
    """Partial edit. Fields left out are unchanged; send null to clear an optional field.

    Money rules (rate, budget, caps, min views) are locked once the campaign is funded,
    because creators joined under those terms and the pool is already paid in.
    """

    title: str | None = None
    description: str | None = None
    requirements: str | None = None
    category: CampaignCategory | None = None
    platforms: list[Platform] | None = None
    thumbnail_url: str | None = None
    rate_per_1k_views: Decimal | None = None
    total_budget: Decimal | None = None
    cap_per_post: Decimal | None = None
    cap_per_profile: Decimal | None = None
    min_views: int | None = None
    deadline: datetime | None = None
    # Funded campaigns only: pause (hidden from Discover, no new submissions) or resume.
    status: Literal[CampaignStatus.active, CampaignStatus.paused] | None = None


class BrandCampaignStats(BaseModel):
    submissions: dict[SubmissionStatus, int]
    creators: int  # distinct creators who submitted
    total_views: int  # views on approved (earning) videos


class BrandCampaign(CampaignDetail):
    """A campaign as its owner sees it on /brand/campaigns."""

    stats: BrandCampaignStats
