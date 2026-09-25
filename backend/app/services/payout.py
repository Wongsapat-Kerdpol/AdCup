"""[PERSON 2] Payout engine — first-come-first-served + flat commission.

Rules (proposal section 6):
  * gross = views / 1000 * campaign.rate_per_1k_views, limited by cap_per_post, cap_per_profile
    and campaign.remaining_budget (pool runs out -> later approvals earn nothing)
  * process submissions in `approved_at` order
  * commission = gross * COMMISSION_RATE (10%), net = gross - commission
  * campaign.paid_out += gross ; creator.wallet_balance += net
  * write a Transaction(type=payout, gross_amount, commission_amount, net_amount)
  * lock the campaign row (SELECT ... FOR UPDATE) so two approvals can't overspend the pool
"""

from decimal import Decimal

from app.core.config import COMMISSION_RATE  # noqa: F401


def split_commission(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Return (commission, net) rounded to satang."""
    commission = (gross * COMMISSION_RATE).quantize(Decimal("0.01"))
    return commission, gross - commission


# TODO(Person 2): def process_payout(db: Session, submission: Submission) -> Transaction | None
