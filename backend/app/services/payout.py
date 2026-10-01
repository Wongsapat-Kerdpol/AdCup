"""Payout engine — settlement rounds, max-min fair split, flat 10% commission.

Money only flows for submissions with status == approved (passed system check AND admin review).
Payouts are INCREMENTAL: a round pays only for the views gained since the last round.

  Example (rate ฿1 / 1K views): approved at 1,000 views -> +฿1 gross; next round at 3,000 -> +฿2 gross.

HOW A ROUND WORKS (replaces first-come-first-served)
  1. demand : every approved video has earned (view_count - paid_views) / 1000 * rate, limited by
              cap_per_post and (per creator) cap_per_profile.
  2. split  : if the pool covers all demands everybody is paid in full. Otherwise the pool is split
              max-min fair (services/allocation.py): small earners are paid in full first, the rest
              share what is left equally. Approval order and refresh timing don't matter.
  3. pay    : 10% commission, net -> creator wallet, one Transaction per video per round.

Refreshing a video only stores its new view count — it never moves money — so pressing the
refresh button earlier or more often gives no advantage. Rounds are run by an admin
(POST /api/admin/payout-round) or at the end of POST /api/youtube/refresh-all, after every
video has been refreshed, so all videos in a round are judged on the same snapshot.

Withdrawal (Person 3) is separate: wallet grows with each round, cash out only when >= MIN_WITHDRAWAL_THB.

Callers manage their own db.commit(); this module only db.flush()es so it never breaks their transaction.
"""

from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import COMMISSION_RATE
from app.models.campaign import Campaign, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.allocation import max_min_fair_share


def split_commission(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Return (commission, net) rounded to satang."""
    commission = (gross * COMMISSION_RATE).quantize(Decimal("0.01"))
    return commission, gross - commission


def to_satang(amount: Decimal) -> int:
    """THB -> integer satang (rounded down), so the split is exact."""
    return int((amount * 100).to_integral_value(rounding=ROUND_DOWN))


def from_satang(satang: int) -> Decimal:
    return (Decimal(satang) / Decimal(100)).quantize(Decimal("0.01"))


def _demands(campaign: Campaign, submissions: list[Submission]) -> list[int]:
    """What each submission has earned since its last payout, in satang, after the caps."""
    demand: dict[int, int] = {}
    for submission in submissions:
        new_views = submission.view_count - submission.paid_views
        if new_views <= 0:
            demand[submission.id] = 0
            continue
        satang = to_satang(Decimal(new_views) / Decimal(1000) * campaign.rate_per_1k_views)
        if campaign.cap_per_post is not None:
            satang = min(satang, max(to_satang(campaign.cap_per_post - submission.gross_amount), 0))
        demand[submission.id] = satang

    if campaign.cap_per_profile is not None:
        # A creator's remaining allowance is shared between their own videos with the same
        # fair-share rule, before the pool is split between creators.
        by_creator: dict[int, list[Submission]] = defaultdict(list)
        for submission in submissions:
            by_creator[submission.creator_id].append(submission)
        for videos in by_creator.values():
            earned = sum(to_satang(v.gross_amount) for v in videos)
            allowance = max(to_satang(campaign.cap_per_profile) - earned, 0)
            capped = max_min_fair_share([demand[v.id] for v in videos], allowance)
            for video, amount in zip(videos, capped):
                demand[video.id] = amount

    return [demand[s.id] for s in submissions]


def settle_campaign(db: Session, campaign_id: int) -> list[Transaction]:
    """Run one payout round for a campaign. Returns the Transactions created (possibly none).

    Idempotent: paid_views advances to view_count for every video that had new views, even if its
    share was cut to 0 by a cap or an empty pool — otherwise those views would be retried as "new"
    in every future round.
    """
    # Lock the campaign row first so two concurrent rounds can't both read the same
    # remaining_budget and jointly overspend the pool.
    # of=Campaign: Campaign.brand is lazy="joined", and Postgres can't lock the outer-joined
    # users row (same fix as routers/payments.py::checkout_campaign).
    campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update(of=Campaign))
    if campaign is None:
        return []

    submissions = list(
        db.scalars(
            select(Submission)
            .where(Submission.campaign_id == campaign.id, Submission.status == SubmissionStatus.approved)
            .order_by(Submission.approved_at.asc().nulls_last(), Submission.id)
        ).all()
    )
    if not submissions:
        return []

    demands = _demands(campaign, submissions)
    granted = max_min_fair_share(demands, to_satang(campaign.remaining_budget))

    transactions: list[Transaction] = []
    for submission, satang in zip(submissions, granted):
        views_from = submission.paid_views
        if submission.view_count <= views_from:
            continue
        submission.paid_views = submission.view_count
        if satang <= 0:
            continue

        gross = from_satang(satang)
        commission, net = split_commission(gross)

        campaign.paid_out += gross
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
        transactions.append(tx)

    if campaign.remaining_budget <= 0:
        campaign.status = CampaignStatus.completed
    db.flush()
    return transactions


def settle_all(db: Session) -> list[Transaction]:
    """One payout round for every campaign that has approved videos with unpaid views."""
    campaign_ids = db.scalars(
        select(Submission.campaign_id)
        .where(Submission.status == SubmissionStatus.approved, Submission.view_count > Submission.paid_views)
        .distinct()
        .order_by(Submission.campaign_id)
    ).all()
    results: list[Transaction] = []
    for campaign_id in campaign_ids:
        results.extend(settle_campaign(db, campaign_id))
    return results
