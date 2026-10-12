"""Linked account detection, Phase 2 — Union-Find, profile groups, payout account, submit guard.
Scenario numbers (S1…) follow docs/linked-account-detection-spec.md, section 10.2."""

from contextlib import nullcontext

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.models.identity import IdentitySignal, LinkFlag, LinkFlagKind, LinkFlagStatus, ManualLink, SignalType
from app.models.user import PayoutMethod, User, UserRole
from app.routers.auth import register
from app.routers.payout_method import get_payout_method, set_payout_method
from app.routers.submissions import PAYOUT_ACCOUNT_REQUIRED, create_submission
from app.schemas.payout_method import PayoutMethodUpdate
from app.schemas.submission import SubmissionCreate
from app.schemas.user import RegisterRequest, UserPublic
from app.seed import seed_if_empty
from app.services.identity import record_signal
from app.services.linking import DSU, rebuild_profile_groups


def _group(db, *users) -> set[int | None]:
    for user in users:
        db.refresh(user)
    return {u.profile_group_id for u in users}


def _share(db, users, signal_type: SignalType, value: str) -> None:
    for user in users:
        record_signal(db, user, signal_type, value)


def _promptpay(db, user, phone: str):
    return set_payout_method(
        PayoutMethodUpdate(method=PayoutMethod.promptpay, promptpay_id=phone, account_name="Ton"), user, db
    )


def _hub_flags(db) -> list[LinkFlag]:
    return list(db.scalars(select(LinkFlag).where(LinkFlag.kind == LinkFlagKind.hub)).all())


# --- DSU ---


def test_dsu_links_transitively_and_ignores_repeated_unions():
    dsu = DSU(range(1, 5))
    dsu.union(1, 2)
    dsu.union(2, 3)
    dsu.union(2, 3)
    assert dsu.find(1) == dsu.find(3)
    assert dsu.find(4) != dsu.find(1)


def test_dsu_union_by_rank_hangs_the_shorter_tree_under_the_taller():
    dsu = DSU(range(1, 5))
    dsu.union(1, 2)  # rank(1) = 1
    dsu.union(3, 1)  # 3 has rank 0 -> goes under 1 even though it was passed first
    assert dsu.parent[3] == 1 and dsu.rank[1] == 1


def test_nine_account_example_from_the_slides():
    dsu = DSU(range(1, 10))
    dsu.union(1, 2)
    dsu.union(2, 3)
    dsu.union(4, 5)
    dsu.union(3, 4)
    assert dsu.parent[5] == 4  # before find: 5 still hangs under its old root
    assert dsu.find(5) == 1
    assert dsu.parent[5] == 1  # path compression: 5 now points straight at the root
    assert {i for i in range(1, 10) if dsu.find(i) == 1} == {1, 2, 3, 4, 5}
    assert len({dsu.find(i) for i in (6, 7, 8, 9)}) == 4  # the IP pair and the device pair were never unioned


def test_ip_and_device_never_merge_groups(db, make_user):
    a, b, c, d = (make_user() for _ in range(4))
    _share(db, [a, b], SignalType.ip, "203.0.113.7")
    _share(db, [c, d], SignalType.device_id, "6f1c2b9e-1d2a-4c3b-8e4f-5a6b7c8d9e0f")
    rebuild_profile_groups(db)
    assert len(_group(db, a, b, c, d)) == 4


# --- rebuild_profile_groups ---


def test_s1_gmail_alias_is_linked_at_sign_up(db):
    def sign_up(email):
        body = RegisterRequest(display_name="Ton", email=email, password="password123", role=UserRole.creator)
        return db.get(User, register(body, db).user.id)

    ton = sign_up("ton@gmail.com")
    shorts = sign_up("t.o.n+shorts@gmail.com")

    assert shorts.profile_group_id == ton.id == ton.profile_group_id  # smallest id in the group
    assert "profile_group_id" not in UserPublic.model_fields  # the creator sees nothing unusual


def test_every_creator_gets_its_own_group_by_default(db, make_user):
    a, b = make_user(), make_user()
    changed = rebuild_profile_groups(db)
    assert changed >= {a.id, b.id}
    assert _group(db, a) == {a.id} and _group(db, b) == {b.id}
    assert rebuild_profile_groups(db) == set()  # nothing changed the second time


def test_s2_s3_google_account_and_promptpay_link_transitively(db, make_user):
    one, two, three = make_user(), make_user(), make_user()
    _share(db, [one, two], SignalType.google_sub, "google-1")  # S2
    rebuild_profile_groups(db)
    assert _group(db, one, two) == {one.id}
    assert _group(db, three) == {three.id}

    _promptpay(db, two, "081-234-5678")  # S3: #2 and #3 are paid to the same PromptPay
    _promptpay(db, three, "0812345678")
    assert _group(db, one, two, three) == {one.id}


def test_s7_google_account_shared_by_many_is_a_hub_and_does_not_link(db, make_user):
    creators = [make_user() for _ in range(6)]  # an agency managing six creators' channels
    _share(db, creators, SignalType.google_sub, "agency")
    rebuild_profile_groups(db)

    assert len(_group(db, *creators)) == 6
    (flag,) = _hub_flags(db)
    assert (flag.signal_type, flag.status, flag.reasons) == (SignalType.google_sub, LinkFlagStatus.open, ["google_sub"])

    # Admin: "agency / manager — ignore this signal" (endpoint in Phase 4) dismisses the value.
    db.execute(update(IdentitySignal).where(IdentitySignal.value_hash == flag.value_hash).values(dismissed=True))
    flag.status = LinkFlagStatus.resolved
    rebuild_profile_groups(db)
    assert len(_group(db, *creators)) == 6
    assert len(_hub_flags(db)) == 1


def test_s8_promptpay_shared_by_many_is_a_hub_but_still_links(db, make_user):
    creators = [make_user() for _ in range(5)]  # mule account
    for creator in creators:
        _promptpay(db, creator, "0899999999")

    assert _group(db, *creators) == {creators[0].id}
    (flag,) = _hub_flags(db)
    assert flag.signal_type == SignalType.payout_account


def test_hub_flag_is_not_raised_again_once_decided(db, make_user):
    creators = [make_user() for _ in range(4)]
    _share(db, creators, SignalType.email_norm, "shared@example.com")
    rebuild_profile_groups(db)
    (flag,) = _hub_flags(db)
    flag.status = LinkFlagStatus.resolved  # admin: "Release withdrawals"
    rebuild_profile_groups(db)
    assert len(_hub_flags(db)) == 1
    assert _group(db, *creators) == {creators[0].id}  # an email still links (spec D6)


def test_three_accounts_sharing_a_value_are_not_a_hub(db, make_user):
    creators = [make_user() for _ in range(3)]
    _share(db, creators, SignalType.google_sub, "google-3")
    rebuild_profile_groups(db)
    assert _hub_flags(db) == []
    assert _group(db, *creators) == {creators[0].id}


def test_manual_link_merges_groups(db, make_user):
    admin = make_user(UserRole.admin)
    a, b = make_user(), make_user()
    db.add(ManualLink(user_a_id=a.id, user_b_id=b.id, admin_id=admin.id))
    db.flush()
    rebuild_profile_groups(db)
    assert _group(db, a, b) == {a.id}


def test_s10_brand_and_creator_with_the_same_email_are_not_linked(db):
    def sign_up(email, role):
        body = RegisterRequest(display_name="Ton", email=email, password="password123", role=role)
        return db.get(User, register(body, db).user.id)

    brand = sign_up("ton@gmail.com", UserRole.brand)
    creator = sign_up("t.o.n@gmail.com", UserRole.creator)
    assert brand.profile_group_id is None
    assert creator.profile_group_id == creator.id


# --- payout account API ---


def test_payout_account_is_masked_and_stored_only_as_a_hash(db, make_user):
    creator = make_user(payout_method=None)
    assert get_payout_method(creator).account is None

    response = _promptpay(db, creator, "081-234-5678")

    assert response.account.method == PayoutMethod.promptpay
    assert response.account.account_masked == "••• 5678"
    assert response.account.account_name == "Ton"
    (signal,) = db.scalars(select(IdentitySignal).where(IdentitySignal.user_id == creator.id)).all()
    assert signal.type == SignalType.payout_account and "5678" not in signal.value_hash


def test_bank_account(db, make_user):
    creator = make_user(payout_method=None)
    body = PayoutMethodUpdate(
        method=PayoutMethod.bank, bank_code="kbank", account_number="123-4-56789-0", account_name="Ton S."
    )
    account = set_payout_method(body, creator, db).account
    assert (account.method, account.bank_code, account.account_masked) == (PayoutMethod.bank, "KBANK", "••• 7890")


@pytest.mark.parametrize(
    "body",
    [
        dict(method=PayoutMethod.promptpay, promptpay_id="12345"),
        dict(method=PayoutMethod.promptpay),
        dict(method=PayoutMethod.bank, bank_code="NOPE", account_number="1234567890"),
        dict(method=PayoutMethod.bank, bank_code="SCB", account_number="12345"),
    ],
)
def test_invalid_payout_account_is_rejected(db, make_user, body):
    creator = make_user(payout_method=None)
    with pytest.raises(HTTPException) as exc:
        set_payout_method(PayoutMethodUpdate(account_name="Ton", **body), creator, db)
    assert exc.value.status_code == 422
    assert creator.payout_method is None


def test_changing_the_payout_account_keeps_the_old_one_linked(db, make_user):
    a, b = make_user(), make_user()
    _promptpay(db, a, "0811111111")
    _promptpay(db, b, "0811111111")
    _promptpay(db, b, "0822222222")  # b switches away — still the same person as a
    assert _group(db, a, b) == {a.id}
    assert len(db.scalars(select(IdentitySignal).where(IdentitySignal.user_id == b.id)).all()) == 2


def test_seeded_creator_can_submit_and_has_its_own_group(db, monkeypatch):
    monkeypatch.setattr("app.seed.SessionLocal", lambda: nullcontext(db))
    seed_if_empty()

    creator = db.scalar(select(User).where(User.email == "creator@adcup.dev"))
    brand = db.scalar(select(User).where(User.email == "brand@adcup.dev"))
    assert creator.payout_method == PayoutMethod.promptpay
    assert creator.profile_group_id == creator.id
    assert brand.profile_group_id is None
    types = db.scalars(select(IdentitySignal.type).where(IdentitySignal.user_id == creator.id)).all()
    assert sorted(types) == [SignalType.email_norm, SignalType.payout_account]


# --- submit guard (spec D8) ---


def test_s9_submitting_without_a_payout_account_is_refused(db, make_campaign, make_user):
    creator = make_user(youtube_channel_id="channel-1", payout_method=None)
    campaign = make_campaign()

    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=campaign.id, video_url="https://youtu.be/xyz12345678"), creator, db)
    assert (exc.value.status_code, exc.value.detail) == (400, PAYOUT_ACCOUNT_REQUIRED)
