from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.models.campaign import CampaignStatus
from app.models.transaction import TransactionStatus, TransactionType


class PaymentMethod(str, Enum):
    """Mock checkout only — no real money moves."""

    promptpay = "promptpay"
    card = "card"


class CheckoutRequest(BaseModel):
    method: PaymentMethod = PaymentMethod.promptpay


class CheckoutResponse(BaseModel):
    campaign_id: int
    campaign_status: CampaignStatus
    transaction_id: int
    reference: str
    amount: Decimal
    method: PaymentMethod
    paid_at: datetime


class WalletTransaction(BaseModel):
    id: int
    type: TransactionType
    status: TransactionStatus
    gross_amount: Decimal
    commission_amount: Decimal
    net_amount: Decimal
    reference: str | None = None
    campaign_id: int | None = None
    campaign_title: str | None = None
    submission_id: int | None = None
    views_from: int | None = None
    views_to: int | None = None
    created_at: datetime


class WalletResponse(BaseModel):
    balance: Decimal
    min_withdrawal: Decimal
    can_withdraw: bool
    total_earned: Decimal  # sum of net payouts
    total_commission: Decimal  # platform's 10% taken from those payouts
    total_withdrawn: Decimal
    transactions: list[WalletTransaction]


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class WithdrawResponse(BaseModel):
    balance: Decimal
    transaction: WalletTransaction
