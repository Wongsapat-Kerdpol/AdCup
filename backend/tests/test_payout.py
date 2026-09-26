"""[PERSON 2] Payout engine tests — the payment-critical core of the app."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.campaign import CampaignStatus
from app.models.submission import SubmissionStatus
from app.models.transaction import TransactionType
from app.models.user import UserRole
from app.services.payout import process_all_payouts, process_payout


def test_basic_increment_matches_readme_example(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"))
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=0
    )

    tx = process_payout(db, submission)

    assert tx is not None
    assert tx.type == TransactionType.payout
    assert tx.gross_amount == Decimal("1.00")
    assert tx.commission_amount == Decimal("0.10")
    assert tx.net_amount == Decimal("0.90")
    assert tx.views_from == 0
    assert tx.views_to == 1000
    assert submission.paid_views == 1000
    assert creator.wallet_balance == Decimal("0.90")
    assert campaign.paid_out == Decimal("1.00")


def test_second_increment_pays_only_new_views(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"))
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=0
    )
    process_payout(db, submission)

    submission.view_count = 3000
    tx = process_payout(db, submission)

    assert tx.gross_amount == Decimal("2.00")
    assert tx.net_amount == Decimal("1.80")
    assert tx.views_from == 1000
    assert tx.views_to == 3000
    assert submission.paid_views == 3000
    assert creator.wallet_balance == Decimal("0.90") + Decimal("1.80")


def test_cap_per_post_clamps_gross(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(
        rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"), cap_per_post=Decimal("0.50")
    )
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=0
    )

    tx = process_payout(db, submission)

    assert tx.gross_amount == Decimal("0.50")
    # capped views must not be retryable — paid_views still advances to view_count
    assert submission.paid_views == 1000


def test_cap_per_profile_clamps_across_submissions(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(
        rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"), cap_per_profile=Decimal("1.00")
    )
    sub1 = make_submission(campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=0)
    sub2 = make_submission(campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=0)

    tx1 = process_payout(db, sub1)
    tx2 = process_payout(db, sub2)

    assert tx1.gross_amount == Decimal("1.00")
    assert tx2 is None  # profile cap already exhausted by sub1
    assert sub2.paid_views == 1000  # still marked paid so it isn't retried forever


def test_pool_exhaustion_clamps_and_completes_campaign(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1.00"))
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.approved, view_count=2000, paid_views=0
    )

    tx = process_payout(db, submission)

    assert tx.gross_amount == Decimal("1.00")
    assert campaign.paid_out == Decimal("1.00")
    assert campaign.remaining_budget == Decimal("0.00")
    assert campaign.status == CampaignStatus.completed


def test_no_new_views_is_a_noop(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.approved, view_count=1000, paid_views=1000
    )

    tx = process_payout(db, submission)

    assert tx is None
    assert creator.wallet_balance == Decimal("0")


def test_not_approved_is_a_noop(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.under_review, view_count=5000, paid_views=0
    )

    assert process_payout(db, submission) is None


def test_process_all_payouts_pays_first_come_first_served(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1.20"))
    now = datetime.now(timezone.utc)
    earlier = make_submission(
        campaign,
        creator,
        status=SubmissionStatus.approved,
        view_count=1000,
        paid_views=0,
        approved_at=now,
    )
    later = make_submission(
        campaign,
        creator,
        status=SubmissionStatus.approved,
        view_count=1000,
        paid_views=0,
        approved_at=now + timedelta(seconds=5),
    )

    results = process_all_payouts(db)

    assert [tx.submission_id for tx in results] == [earlier.id, later.id]
    assert earlier.gross_amount == Decimal("1.00")  # got the full pool first
    assert later.gross_amount == Decimal("0.20")  # only the leftover
    assert campaign.status == CampaignStatus.completed
