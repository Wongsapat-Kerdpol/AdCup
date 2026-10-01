from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class NewcomerOutlook(BaseModel):
    views_per_day: float
    assumption: Literal["input", "median", "default"]  # where views_per_day came from
    expected_gross: Decimal
    expected_net: Decimal  # after the 10% platform fee
    fill_ratio: float | None = None  # 1.0 = the pool can pay everything this video would earn


class CampaignOutlook(BaseModel):
    verdict: Literal["open", "competitive", "crowded", "closed"]
    pool_remaining: Decimal
    horizon_days: int
    projected_claims: Decimal
    pressure: float | None = None
    exhausted_in_days: int | None = None
    exhausted_on: date | None = None
    approved_videos: int
    in_review_videos: int
    newcomer: NewcomerOutlook
