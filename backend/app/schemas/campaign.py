from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.models.campaign import CampaignCategory, CampaignStatus


class CampaignSort(str, Enum):
    newest = "newest"
    highest_rate = "highest_rate"
    highest_budget = "highest_budget"
    most_available = "most_available"  # lowest paid-out %
    ending_soon = "ending_soon"


class BrandSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    avatar_url: str | None = None


class CampaignCard(BaseModel):
    """Everything the shared <CampaignCard> component needs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: CampaignCategory
    platforms: list[str]
    thumbnail_url: str | None = None
    status: CampaignStatus
    total_budget: Decimal
    paid_out: Decimal
    paid_out_percent: float
    remaining_budget: Decimal
    rate_per_1k_views: Decimal
    rate_per_1m_views: Decimal
    deadline: datetime | None = None
    created_at: datetime
    brand: BrandSummary


class CampaignDetail(CampaignCard):
    """Full campaign. Person 1 can extend this for the detail page."""

    description: str
    requirements: str
    cap_per_post: Decimal | None = None
    cap_per_profile: Decimal | None = None
    is_funded: bool


class CampaignListResponse(BaseModel):
    items: list[CampaignCard]
    total: int
    page: int
    page_size: int
