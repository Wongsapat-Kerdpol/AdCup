"""[PERSON 3] Mock checkout (brand funds a campaign) + wallet + withdrawal.

  POST /api/payments/checkout/{campaign_id} — mock payment; set campaign.is_funded=True,
                                              status=active, write Transaction(type=campaign_fund)
  GET  /api/wallet                          — balance + transaction history for current user
  POST /api/wallet/withdraw                 — creator cash out; amount >= MIN_WITHDRAWAL_THB and <= balance
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import MIN_WITHDRAWAL_THB
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.campaign import Campaign, CampaignStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.schemas.payment import (
    CheckoutRequest,
    CheckoutResponse,
    WalletResponse,
    WalletTransaction,
    WithdrawRequest,
    WithdrawResponse,
)

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


def _to_wallet_tx(tx: Transaction, campaign_title: str | None) -> WalletTransaction:
    return WalletTransaction(
        id=tx.id,
        type=tx.type,
        status=tx.status,
        gross_amount=tx.gross_amount,
        commission_amount=tx.commission_amount,
        net_amount=tx.net_amount,
        reference=tx.reference,
        campaign_id=tx.campaign_id,
        campaign_title=campaign_title,
        submission_id=tx.submission_id,
        views_from=tx.views_from,
        views_to=tx.views_to,
        created_at=tx.created_at,
    )


@router.get("/wallet", response_model=WalletResponse)
def get_wallet(
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current user's balance, lifetime totals and latest transactions (newest first)."""
    rows = db.execute(
        select(Transaction, Campaign.title)
        .outerjoin(Campaign, Campaign.id == Transaction.campaign_id)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
    ).all()

    def total(tx_type: TransactionType, column) -> Decimal:
        return db.scalar(
            select(func.coalesce(func.sum(column), 0)).where(
                Transaction.user_id == user.id,
                Transaction.type == tx_type,
                Transaction.status == TransactionStatus.completed,
            )
        )

    return WalletResponse(
        balance=user.wallet_balance,
        min_withdrawal=MIN_WITHDRAWAL_THB,
        can_withdraw=user.role == UserRole.creator and user.wallet_balance >= MIN_WITHDRAWAL_THB,
        total_earned=total(TransactionType.payout, Transaction.net_amount),
        total_commission=total(TransactionType.payout, Transaction.commission_amount),
        total_withdrawn=total(TransactionType.withdrawal, Transaction.net_amount),
        transactions=[_to_wallet_tx(tx, title) for tx, title in rows],
    )


@router.post("/wallet/withdraw", response_model=WithdrawResponse)
def withdraw(
    body: WithdrawRequest,
    user: User = Depends(require_role(UserRole.creator)),
    db: Session = Depends(get_db),
):
    """Mock cash out. No bank transfer happens; the balance and ledger update as if it did."""
    # Re-read the user with a row lock so two withdrawals (or a payout) can't race the balance.
    # populate_existing: `user` is already in this session, so force the locked, fresh balance.
    creator = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )

    if body.amount < MIN_WITHDRAWAL_THB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum withdrawal is ฿{MIN_WITHDRAWAL_THB:,.0f}",
        )
    if body.amount > creator.wallet_balance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount is more than your balance")

    tx = Transaction(
        user_id=creator.id,
        type=TransactionType.withdrawal,
        status=TransactionStatus.completed,
        gross_amount=body.amount,
        commission_amount=Decimal("0"),
        net_amount=body.amount,
        reference=f"MOCK-WD-{uuid.uuid4().hex[:10].upper()}",
    )
    creator.wallet_balance -= body.amount
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return WithdrawResponse(balance=creator.wallet_balance, transaction=_to_wallet_tx(tx, None))
