"""[PERSON 3] Mock checkout (brand funds a campaign) + wallet + withdrawal.

  POST /api/payments/checkout/{campaign_id} — mock payment; set campaign.is_funded=True,
                                              status=active, write Transaction(type=campaign_fund)
TODO(Person 3):
  GET  /api/wallet                          — balance + transaction history for current user
  POST /api/wallet/withdraw                 — only if balance >= MIN_WITHDRAWAL_THB (1,500 THB)
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign, CampaignStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.schemas.payment import CheckoutRequest, CheckoutResponse

router = APIRouter(prefix="/api", tags=["payments & wallet (Person 3)"])


@router.post("/payments/checkout/{campaign_id}", response_model=CheckoutResponse)
def checkout_campaign(
    campaign_id: int,
    body: CheckoutRequest | None = None,
    user: User = Depends(require_role(UserRole.brand)),
    db: Session = Depends(get_db),
):
    """Brand "pays" the full budget into the campaign pool. Simulated: always succeeds."""
    body = body or CheckoutRequest()

    # Lock the row so a double-click can't fund (and record) the campaign twice.
    # of=Campaign: Campaign.brand is lazy="joined", and Postgres can't lock the outer-joined users row.
    campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update(of=Campaign))
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.brand_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only fund your own campaigns")
    if campaign.is_funded:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign is already funded")
    if campaign.total_budget <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign budget must be greater than 0")

    reference = f"MOCK-{body.method.value.upper()}-{uuid.uuid4().hex[:10].upper()}"
    tx = Transaction(
        user_id=user.id,
        campaign_id=campaign.id,
        type=TransactionType.campaign_fund,
        status=TransactionStatus.completed,
        gross_amount=campaign.total_budget,
        commission_amount=Decimal("0"),  # commission is only taken on creator payouts
        net_amount=campaign.total_budget,
        reference=reference,
    )
    campaign.is_funded = True
    campaign.status = CampaignStatus.active
    db.add(tx)
    db.commit()
    db.refresh(tx)

    return CheckoutResponse(
        campaign_id=campaign.id,
        campaign_status=campaign.status,
        transaction_id=tx.id,
        reference=reference,
        amount=tx.gross_amount,
        method=body.method,
        paid_at=tx.created_at,
    )
