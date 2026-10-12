"""Linked account detection, Phase 3 — cap per profile counted per profile group in payout rounds,
and the overage check after linking. Numbers follow docs/linked-account-detection-spec.md, 10.3 and S6."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.identity import LinkFlag, LinkFlagKind, LinkFlagStatus, SignalType
from app.models.submission import SubmissionStatus
from app.models.user import PayoutMethod
from app.routers.payout_method import set_payout_method
from app.schemas.payout_method import PayoutMethodUpdate
from app.services.identity import record_signal
from app.services.linking import rebuild_profile_groups
from app.services.payout import settle_campaign


def approved(make_submission, campaign, creator, views):
    return make_submission(campaign, creator, status=SubmissionStatus.approved, view_count=views, paid_views=0)


def _link(db, *creators):
    for creator in creators:
        record_signal(db, creator, SignalType.email_norm, "ton@gmail.com")
    rebuild_profile_groups(db)


def _overages(db) -> list[LinkFlag]:
    return list(db.scalars(select(LinkFlag).where(LinkFlag.kind == LinkFlagKind.overage)).all())


@pytest.fixture()
def slide_campaign(make_campaign):
    """Pool ฿10,000 · ฿25 / 1,000 views · cap per post ฿1,500 · cap per profile ฿3,000."""
    return make_campaign(
        rate_per_1k_views=Decimal("25.00"),
        total_budget=Decimal("10000.00"),
        cap_per_post=Decimal("1500.00"),
        cap_per_profile=Decimal("3000.00"),
    )


@pytest.fixture()
def slide_videos(slide_campaign, make_user, make_submission):
    """ton and ton_shorts: 2 videos each · beam, cee, dao: 1 each. Every video has 80,000 new views
    (= ฿2,000, ฿1,500 after the cap per post)."""
    ton, shorts, beam, cee, dao = (make_user(display_name=n) for n in ("ton", "ton_shorts", "beam", "cee", "dao"))
    videos = {
        ton: [approved(make_submission, slide_campaign, ton, 80_000) for _ in range(2)],
        shorts: [approved(make_submission, slide_campaign, shorts, 80_000) for _ in range(2)],
    }
    for other in (beam, cee, dao):
        videos[other] = [approved(make_submission, slide_campaign, other, 80_000)]
    return videos


def _paid(videos) -> Decimal:
    return sum((v.gross_amount for v in videos), Decimal("0"))


def test_not_linked_two_accounts_get_two_caps_and_the_pool_is_split(db, slide_campaign, slide_videos):
    ton, shorts, beam, cee, dao = slide_videos

    settle_campaign(db, slide_campaign.id)

    # claims ฿3,000 + ฿3,000 + 3 × ฿1,500 = ฿10,500 > pool -> everybody gets 95.238%
    assert slide_campaign.paid_out == Decimal("10000.00")
    assert slide_campaign.remaining_budget == Decimal("0")
    assert _paid(slide_videos[ton]) + _paid(slide_videos[shorts]) == Decimal("5714.29")  # the leftover satang
    for other in (beam, cee, dao):
        assert _paid(slide_videos[other]) == Decimal("1428.57")


def test_linked_accounts_share_one_cap(db, slide_campaign, slide_videos):
    ton, shorts, beam, cee, dao = slide_videos
    _link(db, ton, shorts)

    settle_campaign(db, slide_campaign.id)

    # ton's group claims ฿6,000 -> cut to its ฿3,000 cap, shared proportionally
    for video in slide_videos[ton] + slide_videos[shorts]:
        assert video.gross_amount == Decimal("750.00")
    for other in (beam, cee, dao):
        assert _paid(slide_videos[other]) == Decimal("1500.00")
    assert slide_campaign.paid_out == Decimal("7500.00")
    assert slide_campaign.remaining_budget == Decimal("2500.00")

    # Next round: the group has used its whole cap, so its new views earn nothing.
    group_videos = slide_videos[ton] + slide_videos[shorts]
    for video in group_videos:
        video.view_count += 80_000
    db.flush()
    paid_to = {tx.submission_id for tx in settle_campaign(db, slide_campaign.id)}
    assert paid_to.isdisjoint(v.id for v in group_videos)
    assert all(v.paid_views == 160_000 for v in group_videos)  # the views are not retried later
    assert slide_campaign.paid_out == Decimal("7500.00")


def test_account_without_a_group_counts_as_its_own_profile(db, make_campaign, make_user, make_submission):
    creator = make_user()
    assert creator.profile_group_id is None
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), cap_per_profile=Decimal("1.00"))
    approved(make_submission, campaign, creator, 5000)

    settle_campaign(db, campaign.id)
    assert campaign.paid_out == Decimal("1.00")


# --- overage (spec 6.4, S6) ---


@pytest.fixture()
def s6(db, make_campaign, make_user, make_submission):
    """#40 and #41 have each been paid their full ฿3,000 cap before anybody knew they are one person."""
    campaign = make_campaign(
        rate_per_1k_views=Decimal("25.00"), total_budget=Decimal("10000.00"), cap_per_profile=Decimal("3000.00")
    )
    first, second = make_user(payout_method=None), make_user(payout_method=None)
    videos = [approved(make_submission, campaign, c, 120_000) for c in (first, second)]
    for creator, phone in ((first, "0811111111"), (second, "0822222222")):
        set_payout_method(
            PayoutMethodUpdate(method=PayoutMethod.promptpay, promptpay_id=phone, account_name="Ton"), creator, db
        )
    settle_campaign(db, campaign.id)
    assert [v.gross_amount for v in videos] == [Decimal("3000.00")] * 2
    return campaign, first, second, videos


def test_s6_linking_after_payout_raises_an_overage_and_stops_paying(db, s6):
    campaign, first, second, videos = s6

    set_payout_method(  # #41 switches to #40's PromptPay
        PayoutMethodUpdate(method=PayoutMethod.promptpay, promptpay_id="0811111111", account_name="Ton"), second, db
    )

    db.refresh(first)
    db.refresh(second)
    assert first.profile_group_id == second.profile_group_id == first.id
    (flag,) = _overages(db)
    assert (flag.campaign_id, flag.amount, flag.status) == (campaign.id, Decimal("3000.00"), LinkFlagStatus.open)
    assert flag.user_a_id == first.id

    for video in videos:
        video.view_count += 40_000
    db.flush()
    assert settle_campaign(db, campaign.id) == []  # nothing is clawed back, but nothing more is paid either
    assert campaign.paid_out == Decimal("6000.00")


def test_overage_flag_is_updated_not_duplicated(db, s6, make_user):
    _, first, second, _ = s6
    _link(db, first, second)
    third = make_user()
    _link(db, third)  # the group grows again; third has earned nothing, so the overage stays ฿3,000

    (flag,) = _overages(db)
    assert flag.amount == Decimal("3000.00")


def test_decided_overage_is_not_raised_again(db, s6):
    _, first, second, _ = s6
    _link(db, first, second)
    (flag,) = _overages(db)
    flag.status = LinkFlagStatus.resolved  # admin: "Keep paid amount"
    rebuild_profile_groups(db)
    assert len(_overages(db)) == 1


def test_linking_within_the_cap_raises_no_overage(db, make_campaign, make_user, make_submission):
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"), cap_per_profile=Decimal("10.00"))
    a, b = make_user(), make_user()
    for creator in (a, b):
        approved(make_submission, campaign, creator, 3000)
    settle_campaign(db, campaign.id)  # ฿3 + ฿3 <= ฿10

    _link(db, a, b)
    assert _overages(db) == []
