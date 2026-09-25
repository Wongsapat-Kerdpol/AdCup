"""[PERSON 2] Payout engine — incremental, first-come-first-served, flat 10% commission.

Money only flows for submissions with status == approved (passed system check AND admin review).
Payouts are INCREMENTAL: each time views are refreshed, pay only for the new views.

TODO(Person 2): def process_payout(db, submission) -> Transaction | None
    new_views = submission.view_count - submission.paid_views            (<= 0 -> nothing to pay)
    gross     = new_views / 1000 * campaign.rate_per_1k_views
    limit gross by:
        cap_per_post    - submission.gross_amount                          (if cap set)
        cap_per_profile - SUM(gross_amount) of this creator in this campaign (if cap set)
        campaign.remaining_budget                                          (pool; FCFS)
    commission, net = split_commission(gross)
    campaign.paid_out      += gross      -> campaign completed when remaining_budget == 0
    submission.gross/commission/net_amount += ...,  paid_views = view_count
        (if a cap/pool cut the amount, still set paid_views = view_count so capped views are never paid later)
    creator.wallet_balance += net
    write Transaction(type=payout, user_id=creator, campaign_id, submission_id,
                      gross_amount, commission_amount, net_amount, views_from, views_to)
    Lock the campaign row (with_for_update()) so two refreshes can't overspend the pool.

  Example (rate ฿1 / 1K views): approved at 1,000 views -> +฿1 gross; refresh at 3,000 -> +฿2 gross.

TODO(Person 2): def process_all_payouts(db) — for a batch refresh, loop approved submissions
    ordered by approved_at ASC (first-come-first-served) and call process_payout on each.

Withdrawal (Person 3) is separate: wallet grows continuously, cash out only when >= MIN_WITHDRAWAL_THB.
"""

from decimal import Decimal

from app.core.config import COMMISSION_RATE


def split_commission(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Return (commission, net) rounded to satang."""
    commission = (gross * COMMISSION_RATE).quantize(Decimal("0.01"))
    return commission, gross - commission
