"""Campaign outlook: when does the pool run dry, and what would a new video earn?"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.submission import SubmissionStatus
from app.models.user import UserRole
from app.services.outlook import CLOSED, COMPETITIVE, CROWDED, OPEN, campaign_outlook

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def approved(make_submission, make_user, campaign, views, days_old):
    return make_submission(
        campaign,
        make_user(UserRole.creator),
        status=SubmissionStatus.approved,
        view_count=views,
        paid_views=0,
        video_published_at=NOW - timedelta(days=days_old),
        approved_at=NOW - timedelta(days=days_old),
    )


def test_campaign_without_videos_is_open(db, make_campaign):
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"))

    outlook = campaign_outlook(db, campaign, now=NOW)

    assert outlook.verdict == OPEN
    assert outlook.approved_videos == 0
    assert outlook.exhausted_in_days is None
    assert outlook.newcomer.assumption == "default"
    assert outlook.newcomer.fill_ratio == 1.0


def test_pool_exhaustion_day_is_found_by_binary_search(db, make_campaign, make_user, make_submission):
    # 1,000 views/day at ฿1 per 1K: claims(t) = 1 + t baht, so a ฿10 pool is claimed on day 9
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("10.00"))
    approved(make_submission, make_user, campaign, views=1000, days_old=1)

    outlook = campaign_outlook(db, campaign, now=NOW)

    assert outlook.exhausted_in_days == 9
    assert outlook.exhausted_on == (NOW + timedelta(days=9)).date()
    assert outlook.horizon_days == 30


def test_backlog_drains_the_pool_before_a_new_video_is_even_approved(db, make_campaign, make_user, make_submission):
    # Five videos have already earned ฿100 each against a ฿10 pool. The very next payout round empties
    # it, two days before a video posted today could be approved — so it would earn nothing.
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("10.00"))
    for _ in range(5):
        approved(make_submission, make_user, campaign, views=100_000, days_old=10)

    outlook = campaign_outlook(db, campaign, now=NOW)

    assert outlook.verdict == CROWDED
    assert outlook.exhausted_in_days == 0
    assert outlook.pressure > 1
    assert outlook.newcomer.expected_gross == Decimal("0.00")
    assert outlook.newcomer.fill_ratio == 0.0


def test_room_to_spare_is_open_and_a_tight_pool_is_competitive(db, make_campaign, make_user, make_submission):
    roomy = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("1000.00"))
    approved(make_submission, make_user, roomy, views=1000, days_old=5)
    assert campaign_outlook(db, roomy, views_per_day=1000, now=NOW).verdict == OPEN

    # The existing video (10 views/day) claims ฿1.23 by day 23, the newcomer (1,000 views/day, approved
    # on day 2) ฿23. In round 24 only ฿0.77 is left: the 1-satang claim is paid, the newcomer gets ฿0.76 of
    # its ฿1.00 -> ฿23.76 of the ฿30 it would have earned.
    tight = make_campaign(rate_per_1k_views=Decimal("1.00"), total_budget=Decimal("25.00"))
    approved(make_submission, make_user, tight, views=1000, days_old=100)
    outlook = campaign_outlook(db, tight, views_per_day=1000, now=NOW)
    assert outlook.verdict == COMPETITIVE
    assert outlook.newcomer.expected_gross == Decimal("23.76")
    assert outlook.newcomer.fill_ratio == 0.792


def test_empty_pool_is_closed(db, make_campaign):
    campaign = make_campaign(total_budget=Decimal("10.00"))
    campaign.paid_out = Decimal("10.00")

    assert campaign_outlook(db, campaign, now=NOW).verdict == CLOSED


def test_campaign_ending_before_a_new_video_could_be_approved_is_closed(db, make_campaign):
    campaign = make_campaign(deadline=NOW + timedelta(days=1))

    assert campaign_outlook(db, campaign, now=NOW).verdict == CLOSED
