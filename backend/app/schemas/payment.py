from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel

from app.models.campaign import CampaignStatus


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
