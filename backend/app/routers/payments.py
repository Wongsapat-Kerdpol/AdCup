"""[PERSON 3] Mock checkout (brand funds a campaign) + wallet + withdrawal.

TODO(Person 3):
  POST /api/payments/checkout/{campaign_id} — mock payment; set campaign.is_funded=True,
                                              status=active, write Transaction(type=campaign_fund)
  GET  /api/wallet                          — balance + transaction history for current user
  POST /api/wallet/withdraw                 — only if balance >= MIN_WITHDRAWAL_THB (1,500 THB)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["payments & wallet (Person 3)"])
