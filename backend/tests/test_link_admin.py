"""Linked account detection, Phase 4 — admin endpoints (routers/linked_accounts.py), withdrawal holds and the
extra review queue fields. Scenario numbers follow docs/linked-account-detection-spec.md, 10.2."""

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.identity import IdentitySignal, LinkFlag, LinkFlagKind, LinkFlagStatus, SignalType
from app.models.submission import SubmissionStatus
from app.models.user import UserRole
from app.routers.linked_accounts import confirm, dismiss, ignore_signal, list_links, release, resolve_overage
from app.routers.payments import get_wallet, withdraw
from app.routers.review import review_queue
from app.schemas.linked_accounts import OverageDecision
from app.schemas.payment import WithdrawRequest
from app.services.identity import hash_signal, record_signal
from app.services.linking import rebuild_profile_groups
from app.services.payout import settle_campaign

RICH = {"wallet_balance": Decimal("5000.00")}


@pytest.fixture()
def admin(make_user):
    return make_user(UserRole.admin)


def _share(db, users, signal_type: SignalType, value: str):
    for user in users:
        record_signal(db, user, signal_type, value)
    rebuild_profile_groups(db)


def _flag(db, kind: LinkFlagKind) -> LinkFlag:
    (flag,) = db.scalars(select(LinkFlag).where(LinkFlag.kind == kind)).all()
    return flag


def _held(db, creator) -> bool:
    wallet = get_wallet(100, creator, db)
    try:
        withdraw(WithdrawRequest(amount=Decimal("1500.00")), creator, db)
    except HTTPException as exc:
        assert exc.status_code == 409
        assert wallet.withdrawals_on_hold and not wallet.can_withdraw
        return True
    assert not wallet.withdrawals_on_hold and wallet.can_withdraw
    return False


def _suspected_pair(db, make_user):
    a, b = make_user(**RICH), make_user(**RICH)
    flag = LinkFlag(kind=LinkFlagKind.suspected, user_a_id=a.id, user_b_id=b.id, score=60, reasons=["device_id", "ip"])
    db.add(flag)
    db.flush()
    return a, b, flag


# --- hubs (S7, S8, spec D6) ---


def test_s7_agency_google_account_ignore_signal(db, make_user, admin):
    creators = [make_user(**RICH) for _ in range(6)]
    _share(db, creators, SignalType.google_sub, "agency")
    flag = _flag(db, LinkFlagKind.hub)
    assert not _held(db, creators[0])  # a Google hub only alerts admins (D6)

    out = ignore_signal(flag.id, admin, db)

    assert out.status == LinkFlagStatus.resolved and len(out.users) == 6
    dismissed = db.scalars(select(IdentitySignal.dismissed).where(IdentitySignal.type == SignalType.google_sub)).all()
    assert dismissed == [True] * 6
    for creator in creators:
        db.refresh(creator)
    assert len({c.profile_group_id for c in creators}) == 6


def test_email_hub_ignore_signal_splits_the_group_again(db, make_user, admin):
    creators = [make_user() for _ in range(4)]
    _share(db, creators, SignalType.email_norm, "shared@example.com")
    assert len({c.profile_group_id for c in creators}) == 1

    ignore_signal(_flag(db, LinkFlagKind.hub).id, admin, db)

    for creator in creators:
        db.refresh(creator)
    assert len({c.profile_group_id for c in creators}) == 4


def test_s8_mule_payout_account_holds_withdrawals_until_released(db, make_user, admin):
    creators = [make_user(**RICH) for _ in range(5)]
    _share(db, creators, SignalType.payout_account, "+66899999999")
    flag = _flag(db, LinkFlagKind.hub)
    assert all(_held(db, c) for c in creators)

    with pytest.raises(HTTPException) as exc:
        ignore_signal(flag.id, admin, db)  # spec D17: a payee can't be ignored
    assert exc.value.status_code == 409

    release(flag.id, admin, db)
    assert not _held(db, creators[0])
    assert len({c.profile_group_id for c in creators}) == 1  # still one profile


def test_release_is_only_for_payout_hubs(db, make_user, admin):
    _share(db, [make_user() for _ in range(4)], SignalType.google_sub, "agency")
    with pytest.raises(HTTPException) as exc:
        release(_flag(db, LinkFlagKind.hub).id, admin, db)
    assert exc.value.status_code == 409


# --- suspected ---


def test_suspected_holds_both_accounts_until_dismissed(db, make_user, admin):
    a, b, flag = _suspected_pair(db, make_user)
    assert _held(db, a) and _held(db, b)

    out = dismiss(flag.id, admin, db)

    assert (out.status, [u.id for u in out.users]) == (LinkFlagStatus.dismissed, [a.id, b.id])
    assert flag.decided_by_id == admin.id and flag.decided_at is not None
    assert not _held(db, a) and not _held(db, b)


def test_a_decided_flag_cant_be_decided_again(db, make_user, admin):
    _, _, flag = _suspected_pair(db, make_user)
    confirm(flag.id, admin, db)
    for action in (confirm, dismiss):
        with pytest.raises(HTTPException) as exc:
            action(flag.id, admin, db)
        assert exc.value.status_code == 409


def test_actions_check_the_flag_kind_and_existence(db, make_user, admin):
    _, _, flag = _suspected_pair(db, make_user)
    with pytest.raises(HTTPException) as exc:
        release(flag.id, admin, db)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        dismiss(999_999, admin, db)
    assert exc.value.status_code == 404


# --- overage (S6) ---


def test_overage_holds_the_group_until_kept(db, make_campaign, make_user, make_submission, admin):
    campaign = make_campaign(
        rate_per_1k_views=Decimal("25.00"), cap_per_profile=Decimal("3000.00"), total_budget=Decimal("10000.00")
    )
    a, b = make_user(**RICH), make_user(**RICH)
    for creator in (a, b):
        make_submission(campaign, creator, status=SubmissionStatus.approved, view_count=120_000, paid_views=0)
    settle_campaign(db, campaign.id)
    _share(db, [a, b], SignalType.payout_account, "+66811111111")

    flag = _flag(db, LinkFlagKind.overage)
    assert _held(db, a) and _held(db, b)

    out = resolve_overage(flag.id, OverageDecision(action="keep"), admin, db)

    assert (out.amount, out.group_gross) == (Decimal("3000.00"), Decimal("6000.00"))
    assert out.cap_per_profile == Decimal("3000.00")
    assert out.status == LinkFlagStatus.resolved
    assert not _held(db, a)


def test_reverse_is_not_offered_yet():
    with pytest.raises(ValueError):
        OverageDecision(action="reverse")


# --- GET /api/admin/links ---


def test_list_links_shows_open_flags_and_groups_without_values(db, make_user, admin):
    one, two = make_user(display_name="ton"), make_user(display_name="ton_shorts")
    _share(db, [one, two], SignalType.email_norm, "ton@gmail.com")
    _, _, suspected = _suspected_pair(db, make_user)
    decided = LinkFlag(kind=LinkFlagKind.suspected, user_a_id=one.id, user_b_id=two.id, status=LinkFlagStatus.dismissed)
    db.add(decided)
    db.flush()

    links = list_links(admin, db)

    assert [f.id for f in links.flags] == [suspected.id]  # open flags only
    (group,) = links.groups
    assert (group.group_id, [m.display_name for m in group.members], group.matched) == (
        one.id,
        ["ton", "ton_shorts"],
        ["email_norm"],
    )
    payload = links.model_dump_json()
    assert "ton@gmail.com" not in payload
    assert hash_signal(SignalType.email_norm, "ton@gmail.com") not in payload


# --- review queue ---


def test_review_queue_shows_linked_accounts_and_open_flags(db, make_campaign, make_user, make_submission, admin):
    campaign = make_campaign(cap_per_profile=Decimal("3000.00"))
    ton, shorts, sibling = make_user(display_name="ton"), make_user(display_name="ton_shorts"), make_user()
    _share(db, [ton, shorts], SignalType.payout_account, "+66812345678")
    make_submission(campaign, ton, status=SubmissionStatus.approved, gross_amount=Decimal("1200.00"))
    queued = make_submission(campaign, shorts, status=SubmissionStatus.under_review)
    make_submission(campaign, sibling, status=SubmissionStatus.under_review)
    flag = LinkFlag(
        kind=LinkFlagKind.suspected,
        user_a_id=shorts.id,
        user_b_id=sibling.id,
        campaign_id=campaign.id,
        score=60,
        reasons=["device_id", "ip"],
    )
    db.add(flag)
    db.flush()

    item = next(i for i in review_queue(admin, db) if i.id == queued.id)

    (linked,) = item.linked_accounts
    assert (linked.user_id, linked.display_name, linked.matched) == (ton.id, "ton", ["payout_account"])
    assert (item.group_gross_in_campaign, item.cap_per_profile) == (Decimal("1200.00"), Decimal("3000.00"))
    (open_flag,) = item.open_flags
    assert (open_flag.id, open_flag.kind, open_flag.other_user_id, open_flag.score) == (
        flag.id,
        LinkFlagKind.suspected,
        sibling.id,
        60,
    )


def test_review_queue_is_unchanged_for_an_unlinked_creator(db, make_campaign, make_user, make_submission, admin):
    campaign = make_campaign()
    queued = make_submission(campaign, make_user(), status=SubmissionStatus.under_review)
    item = next(i for i in review_queue(admin, db) if i.id == queued.id)
    assert (item.linked_accounts, item.open_flags, item.group_gross_in_campaign) == ([], [], Decimal("0"))
