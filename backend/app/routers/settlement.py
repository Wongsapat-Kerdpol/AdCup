"""Payout rounds — the only place (besides refresh-all) where money moves to creators.

  POST /api/admin/payout-round — admin: pay every approved video for the views it has gained since
                                  its last payout, using the views already stored (no YouTube calls).
                                  If a campaign's pool can't cover everyone, every video gets the same percentage of what it earned
                                  (see services/payout.py and services/allocation.py).
"""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.schemas.settlement import PayoutRoundResult
from app.services.payout import settle_all

router = APIRouter(prefix="/api/admin", tags=["payout rounds"])


@router.post("/payout-round", response_model=PayoutRoundResult)
def run_payout_round(_: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    transactions = settle_all(db)
    db.commit()
    return PayoutRoundResult(
        campaigns_settled=len({tx.campaign_id for tx in transactions}),
        payouts=len(transactions),
        total_gross=sum((tx.gross_amount for tx in transactions), Decimal("0")),
        total_net=sum((tx.net_amount for tx in transactions), Decimal("0")),
    )
