"""Payout engine tests — payout rounds with a proportional split of the pool."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.campaign import CampaignStatus
from app.models.submission import SubmissionStatus
from app.models.transaction import TransactionType
from app.models.user import UserRole
from app.services.payout import settle_all, settle_campaign


def approved(make_submission, campaign, creator, views, **kwargs):
    return make_submission(campaign, creator, status=SubmissionStatus.approved, view_count=views, paid_views=0, **kwargs)


def test_basic_round_matches_readme_example(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"))
    submission = approved(make_submission, campaign, creator, 1000)

    [tx] = settle_campaign(db, campaign.id)

    assert tx.type == TransactionType.payout
    assert tx.gross_amount == Decimal("1.00")
    assert tx.commission_amount == Decimal("0.10")
    assert tx.net_amount == Decimal("0.90")
    assert tx.views_from == 0
    assert tx.views_to == 1000
    assert submission.paid_views == 1000
    assert creator.wallet_balance == Decimal("0.90")
    assert campaign.paid_out == Decimal("1.00")


def test_second_round_pays_only_new_views(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"))
    submission = approved(make_submission, campaign, creator, 1000)
    settle_campaign(db, campaign.id)

    submission.view_count = 3000
    [tx] = settle_campaign(db, campaign.id)

    assert tx.gross_amount == Decimal("2.00")
    assert tx.net_amount == Decimal("1.80")
    assert (tx.views_from, tx.views_to) == (1000, 3000)
    assert creator.wallet_balance == Decimal("0.90") + Decimal("1.80")


def test_cap_per_post_clamps_gross(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(
        rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"), cap_per_post=Decimal("0.50")
    )
    submission = approved(make_submission, campaign, creator, 1000)

    [tx] = settle_campaign(db, campaign.id)

    assert tx.gross_amount == Decimal("0.50")
    assert submission.paid_views == 1000  # capped views must not be retried


def test_cap_per_profile_is_shared_between_a_creators_videos(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(
        rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"), cap_per_profile=Decimal("1.00")
    )
    sub1 = approved(make_submission, campaign, creator, 1000)
    sub2 = approved(make_submission, campaign, creator, 1000)

    settle_campaign(db, campaign.id)

    assert sub1.gross_amount == Decimal("0.50")
    assert sub2.gross_amount == Decimal("0.50")  # 1.00 allowance shared proportionally, not first video takes all
    assert creator.wallet_balance == Decimal("0.90")


def test_pool_exhaustion_completes_campaign(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1.00"))
    approved(make_submission, campaign, creator, 2000)

    [tx] = settle_campaign(db, campaign.id)

    assert tx.gross_amount == Decimal("1.00")
    assert campaign.remaining_budget == Decimal("0.00")
    assert campaign.status == CampaignStatus.completed


def test_short_pool_is_split_proportionally(db, make_campaign, make_user, make_submission):
    """Earned 0.50 / 2.00 / 5.00 (7.50 in total) from a pool of 3.00: everybody gets 40% of what they earned."""
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("3.00"))
    small, medium, large = (approved(make_submission, campaign, make_user(UserRole.creator), v) for v in (500, 2000, 5000))

    settle_campaign(db, campaign.id)

    assert small.gross_amount == Decimal("0.20")
    assert medium.gross_amount == Decimal("0.80")
    assert large.gross_amount == Decimal("2.00")
    assert campaign.paid_out == Decimal("3.00")


def test_split_does_not_depend_on_approval_order(db, make_campaign, make_user, make_submission):
    now = datetime.now(timezone.utc)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("2.00"))
    early = approved(make_submission, campaign, make_user(UserRole.creator), 2000, approved_at=now)
    late = approved(make_submission, campaign, make_user(UserRole.creator), 2000, approved_at=now + timedelta(days=3))

    settle_campaign(db, campaign.id)

    assert early.gross_amount == late.gross_amount == Decimal("1.00")  # not 2.00 / 0.00


def test_views_cut_by_an_empty_pool_are_not_retried(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1.00"))
    campaign.paid_out = Decimal("1.00")
    submission = approved(make_submission, campaign, creator, 5000)

    assert settle_campaign(db, campaign.id) == []
    assert submission.paid_views == 5000
    assert creator.wallet_balance == Decimal("0")


def test_no_new_views_is_a_noop(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    make_submission(campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=1000)

    assert settle_campaign(db, campaign.id) == []
    assert creator.wallet_balance == Decimal("0")


def test_only_approved_videos_are_paid(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    for status in (SubmissionStatus.pending, SubmissionStatus.under_review, SubmissionStatus.rejected):
        make_submission(campaign, creator, status=status, view_count=5000, paid_views=0)

    assert settle_campaign(db, campaign.id) == []
    assert settle_all(db) == []


def test_settle_all_runs_a_round_for_every_campaign(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    first = make_campaign(rate_per_1k_views=Decimal("1.00"))
    second = make_campaign(rate_per_1k_views=Decimal("2.00"))
    approved(make_submission, first, creator, 1000)
    approved(make_submission, second, creator, 1000)

    transactions = settle_all(db)

    assert {tx.campaign_id for tx in transactions} == {first.id, second.id}
    assert creator.wallet_balance == Decimal("2.70")
