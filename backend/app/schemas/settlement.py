from decimal import Decimal

from pydantic import BaseModel


class PayoutRoundResult(BaseModel):
    campaigns_settled: int
    payouts: int
    total_gross: Decimal
    total_net: Decimal
