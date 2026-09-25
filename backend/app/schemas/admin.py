from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.campaign import CampaignStatus
from app.models.submission import SubmissionStatus
from app.models.user import UserRole


class UserStats(BaseModel):
    total: int
    by_role: dict[UserRole, int]
    new_last_30d: int
    active_last_30d: int  # made a submission or had a transaction in the last 30 days


class MoneyStats(BaseModel):
    total_funded: Decimal  # brands' mock checkouts
    total_paid_out: Decimal  # gross payouts to creators
    commission_revenue: Decimal  # platform's 10% of those payouts (actual revenue)
    total_withdrawn: Decimal
    locked_in_pools: Decimal  # remaining budget of funded, active campaigns
    projected_commission: Decimal  # locked_in_pools x commission rate, if every pool is paid out
    transaction_count: int


class DailyVolume(BaseModel):
    day: date
    paid_out: Decimal
    commission: Decimal
    funded: Decimal


class CampaignPerformance(BaseModel):
    id: int
    title: str
    brand_name: str
    status: CampaignStatus
    total_budget: Decimal
    paid_out: Decimal
    paid_out_percent: float
    submissions: int
    approved: int
    views: int  # sum of view_count across approved submissions


class AdminStats(BaseModel):
    users: UserStats
    money: MoneyStats
    daily: list[DailyVolume]  # last 14 days, oldest first, zero-filled
    submissions_by_status: dict[SubmissionStatus, int]
    campaigns_by_status: dict[CampaignStatus, int]
    top_campaigns: list[CampaignPerformance]
