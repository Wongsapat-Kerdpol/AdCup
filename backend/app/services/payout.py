"""[PERSON 2] Payout engine — incremental, first-come-first-served, flat 10% commission.

Money only flows for submissions with status == approved (passed system check AND admin review).
Payouts are INCREMENTAL: each time views are refreshed, pay only for the new views.

  Example (rate ฿1 / 1K views): approved at 1,000 views -> +฿1 gross; refresh at 3,000 -> +฿2 gross.

Withdrawal (Person 3) is separate: wallet grows continuously, cash out only when >= MIN_WITHDRAWAL_THB.

Called only by routers/review.py (on approve) and app.services.youtube.refresh_views() — both
manage their own db.commit(); this module only db.flush()es so it never breaks their transaction.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import COMMISSION_RATE
from app.models.campaign import Campaign, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User


def split_commission(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Return (commission, net) rounded to satang."""
    commission = (gross * COMMISSION_RATE).quantize(Decimal("0.01"))
    return commission, gross - commission


def process_payout(db: Session, submission: Submission) -> Transaction | None:
    """Pay for the views this submission has accrued since its last payout, if any.

    Returns the new Transaction, or None if there was nothing to pay (not approved, no new
    views, or every new view was cut by a cap/exhausted pool). Idempotent to call repeatedly —
    paid_views always advances to view_count so the same views are never paid twice.
    """
    # Lock the campaign row first so two concurrent refreshes can't both read the same
    # remaining_budget and jointly overspend the pool.
    campaign = db.scalar(select(Campaign).where(Campaign.id == submission.campaign_id).with_for_update())

    if submission.status != SubmissionStatus.approved:
        return None

    new_views = submission.view_count - submission.paid_views
    if new_views <= 0:
        return None

    gross = (Decimal(new_views) / Decimal(1000)) * campaign.rate_per_1k_views

    if campaign.cap_per_post is not None:
        remaining_post_cap = campaign.cap_per_post - submission.gross_amount
        gross = min(gross, max(remaining_post_cap, Decimal("0")))

    if campaign.cap_per_profile is not None:
        creator_gross_so_far = db.scalar(
            select(func.coalesce(func.sum(Submission.gross_amount), 0)).where(
                Submission.campaign_id == campaign.id,
                Submission.creator_id == submission.creator_id,
            )
        )
        remaining_profile_cap = campaign.cap_per_profile - creator_gross_so_far
        gross = min(gross, max(remaining_profile_cap, Decimal("0")))

    gross = min(gross, campaign.remaining_budget)
    gross = gross.quantize(Decimal("0.01"))

    # Always advance paid_views, even if gross was clamped to 0 — otherwise views cut by a
    # cap/pool would be retried as "new" on every future refresh.
    views_from = submission.paid_views
    submission.paid_views = submission.view_count

    if gross <= 0:
        db.flush()
        return None

    commission, net = split_commission(gross)

    campaign.paid_out += gross
    if campaign.remaining_budget <= 0:
        campaign.status = CampaignStatus.completed

    submission.gross_amount += gross
    submission.commission_amount += commission
    submission.net_amount += net

    creator = db.get(User, submission.creator_id)
    creator.wallet_balance += net

    tx = Transaction(
        user_id=creator.id,
        campaign_id=campaign.id,
        submission_id=submission.id,
        type=TransactionType.payout,
        status=TransactionStatus.completed,
        gross_amount=gross,
        commission_amount=commission,
        net_amount=net,
        views_from=views_from,
        views_to=submission.view_count,
    )
    db.add(tx)
    db.flush()
    return tx


def process_all_payouts(db: Session) -> list[Transaction]:
    """Batch refresh: pay every approved submission, oldest approval first (FCFS)."""
    submissions = db.scalars(
        select(Submission)
        .where(Submission.status == SubmissionStatus.approved)
        .order_by(Submission.approved_at.asc().nulls_last(), Submission.id)
    ).all()
    results = []
    for submission in submissions:
        tx = process_payout(db, submission)
        if tx is not None:
            results.append(tx)
    return results
