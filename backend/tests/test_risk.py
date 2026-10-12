"""Linked account detection, Phase 4 — weak-signal risk score (services/risk.py) and the S4 / S5 scenarios
of docs/linked-account-detection-spec.md (10.1, 10.2)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.models.identity import LinkFlag, LinkFlagKind, LinkFlagStatus, SignalType
from app.models.submission import Submission, SubmissionStatus
from app.models.user import UserRole
from app.routers.linked_accounts import confirm, dismiss
from app.routers.payments import WITHDRAWALS_ON_HOLD, withdraw
from app.routers.submissions import create_submission
from app.schemas.payment import WithdrawRequest
from app.schemas.submission import SubmissionCreate
from app.services.identity import record_signal
from app.services.linking import rebuild_profile_groups
from app.services.risk import flag_suspected_links, score_pair

DEVICE = "6f1c2b9e-1d2a-4c3b-8e4f-5a6b7c8d9e0f"
HOME_IP = "203.0.113.7"
NOW = datetime.now(timezone.utc)


def _account(make_user, days_ago: float, **kwargs):
    """A creator who signed up `days_ago` days ago, so sharing an IP now is not "right after sign-up"."""
    return make_user(created_at=NOW - timedelta(days=days_ago), **kwargs)


def _share(db, users, signal_type: SignalType, value: str):
    for user in users:
        record_signal(db, user, signal_type, value)


def _submit(make_submission, campaign, creator, hours_ago: float = 0, **kwargs):
    return make_submission(
        campaign, creator, status=SubmissionStatus.under_review, created_at=NOW - timedelta(hours=hours_ago), **kwargs
    )


def _suspected(db) -> list[LinkFlag]:
    return list(db.scalars(select(LinkFlag).where(LinkFlag.kind == LinkFlagKind.suspected)).all())


@pytest.fixture()
def pair(make_user):
    """Two accounts that signed up 10 days apart."""
    return _account(make_user, 30), _account(make_user, 20)


# --- score_pair (spec D5, D7) ---


def test_same_device_alone_scores_50_and_is_flagged(db, make_campaign, make_submission, pair):
    a, b = pair
    campaign = make_campaign()
    _share(db, pair, SignalType.device_id, DEVICE)
    _submit(make_submission, campaign, a, hours_ago=5)
    submission = _submit(make_submission, campaign, b)

    assert score_pair(db, b, a, campaign.id) == (50, ["device_id"])
    (flag,) = flag_suspected_links(db, submission)
    assert (flag.user_a_id, flag.user_b_id) == (a.id, b.id)
    assert (flag.score, flag.reasons, flag.status) == (50, ["device_id"], LinkFlagStatus.open)
    assert flag.campaign_id == campaign.id


def test_same_ip_alone_scores_10_and_is_not_flagged(db, make_campaign, make_submission, pair):
    a, b = pair
    campaign = make_campaign()
    _share(db, pair, SignalType.ip, HOME_IP)
    _submit(make_submission, campaign, a, hours_ago=5)
    submission = _submit(make_submission, campaign, b)

    assert score_pair(db, b, a, campaign.id) == (10, ["ip"])
    assert flag_suspected_links(db, submission) == []


def test_same_ip_right_after_sign_up_scores_20(db, make_campaign, make_user):
    a = _account(make_user, 3)
    b = make_user()  # signed up just now, already on a's IP
    _share(db, [a, b], SignalType.ip, HOME_IP)
    assert score_pair(db, b, a, make_campaign().id) == (20, ["ip"])


def test_ip_shared_by_more_than_five_accounts_scores_nothing(db, make_campaign, make_user, pair):
    others = [_account(make_user, 10) for _ in range(4)]  # 6 accounts on one IP: a dorm, not a household
    _share(db, [*pair, *others], SignalType.ip, HOME_IP)
    assert score_pair(db, pair[1], pair[0], make_campaign().id) == (0, [])


def test_device_used_by_more_than_three_accounts_scores_nothing(db, make_campaign, make_user, pair):
    others = [_account(make_user, 10) for _ in range(2)]  # 4 accounts on one device: an internet café PC
    _share(db, [*pair, *others], SignalType.device_id, DEVICE)
    _share(db, pair, SignalType.ip, HOME_IP)
    assert score_pair(db, pair[1], pair[0], make_campaign().id) == (10, ["ip"])


def test_sign_up_and_submit_times_add_points(db, make_campaign, make_submission, make_user):
    a = _account(make_user, 30)
    b = make_user(created_at=a.created_at + timedelta(minutes=5))
    campaign = make_campaign()
    _share(db, [a, b], SignalType.device_id, DEVICE)
    _submit(make_submission, campaign, a, hours_ago=0.5)
    _submit(make_submission, campaign, b)
    assert score_pair(db, b, a, campaign.id) == (70, ["device_id", "signup_time", "submit_time"])


def test_timing_alone_scores_nothing_without_a_shared_value(db, make_campaign, make_submission, make_user):
    a = _account(make_user, 30)
    b = make_user(created_at=a.created_at + timedelta(minutes=1))
    campaign = make_campaign()
    _submit(make_submission, campaign, a)
    _submit(make_submission, campaign, b)
    assert score_pair(db, b, a, campaign.id) == (0, [])


# --- which pairs are scored ---


def test_only_pairs_in_the_same_campaign_are_scored(db, make_campaign, make_submission, pair):
    a, b = pair
    _share(db, pair, SignalType.device_id, DEVICE)
    _submit(make_submission, make_campaign(), a)
    submission = _submit(make_submission, make_campaign(), b)
    assert flag_suspected_links(db, submission) == []


def test_rejected_submissions_dont_count(db, make_campaign, make_submission, pair):
    a, b = pair
    campaign = make_campaign()
    _share(db, pair, SignalType.device_id, DEVICE)
    make_submission(campaign, a, status=SubmissionStatus.rejected)
    assert flag_suspected_links(db, _submit(make_submission, campaign, b)) == []


def test_accounts_already_in_one_group_are_not_flagged(db, make_campaign, make_submission, pair):
    a, b = pair
    campaign = make_campaign()
    _share(db, pair, SignalType.email_norm, "ton@gmail.com")
    rebuild_profile_groups(db)
    _share(db, pair, SignalType.device_id, DEVICE)
    _submit(make_submission, campaign, a)
    assert flag_suspected_links(db, _submit(make_submission, campaign, b)) == []


def test_open_flag_is_not_duplicated(db, make_campaign, make_submission, pair):
    a, b = pair
    campaign = make_campaign()
    _share(db, pair, SignalType.device_id, DEVICE)
    _submit(make_submission, campaign, a, hours_ago=5)
    flag_suspected_links(db, _submit(make_submission, campaign, b))
    flag_suspected_links(db, _submit(make_submission, campaign, b, hours_ago=3))
    assert len(_suspected(db)) == 1


def test_dismissed_pair_comes_back_only_with_new_evidence(db, make_campaign, make_submission, pair):
    a, b = pair
    campaign = make_campaign()
    _share(db, pair, SignalType.device_id, DEVICE)
    _submit(make_submission, campaign, a, hours_ago=5)
    (flag,) = flag_suspected_links(db, _submit(make_submission, campaign, b))
    flag.status = LinkFlagStatus.dismissed

    assert flag_suspected_links(db, _submit(make_submission, campaign, b, hours_ago=3)) == []  # same evidence

    _share(db, pair, SignalType.ip, HOME_IP)  # new evidence: they also share an IP now
    (again,) = flag_suspected_links(db, _submit(make_submission, campaign, b, hours_ago=2))
    assert again.reasons == ["device_id", "ip"]


# --- scenarios through the real submit route ---


@pytest.fixture()
def submit_via_route(db, monkeypatch, video_info_factory):
    def _submit_route(campaign, creator, video_id):
        monkeypatch.setattr(
            "app.services.youtube.get_video_info",
            lambda vid: video_info_factory(video_id=vid, channel_id=creator.youtube_channel_id),
        )
        body = SubmissionCreate(campaign_id=campaign.id, video_url=f"https://youtu.be/{video_id}")
        return create_submission(body, creator, db)

    return _submit_route


def test_s4_roommates_on_a_busy_ip_are_not_linked(db, make_campaign, make_user, submit_via_route):
    campaign = make_campaign()
    roommates = [_account(make_user, 30 - i, youtube_channel_id=f"chan-{i}") for i in range(6)]  # stands in for 37
    _share(db, roommates, SignalType.ip, HOME_IP)

    for i, roommate in enumerate(roommates):
        assert submit_via_route(campaign, roommate, f"video{i:06d}").status == SubmissionStatus.under_review

    assert _suspected(db) == []
    rebuild_profile_groups(db)
    assert len({r.profile_group_id for r in roommates}) == 6  # caps stay separate


@pytest.fixture()
def siblings(db, make_campaign, make_user, submit_via_route):
    """S5: two siblings on one family PC and the home IP, both submit to the same campaign."""
    campaign = make_campaign()
    older = _account(make_user, 30, youtube_channel_id="chan-1", wallet_balance=Decimal("2000.00"))
    younger = _account(make_user, 20, youtube_channel_id="chan-2", wallet_balance=Decimal("2000.00"))
    _share(db, [older, younger], SignalType.device_id, DEVICE)
    _share(db, [older, younger], SignalType.ip, HOME_IP)
    rebuild_profile_groups(db)

    first = submit_via_route(campaign, older, "videoAAAAAA")
    db.execute(update(Submission).where(Submission.id == first.id).values(created_at=NOW - timedelta(hours=5)))
    submit_via_route(campaign, younger, "videoBBBBBB")
    return older, younger


def _can_withdraw(db, creator) -> bool:
    try:
        withdraw(WithdrawRequest(amount=Decimal("1500.00")), creator, db)
    except HTTPException as exc:
        assert (exc.status_code, exc.detail) == (409, WITHDRAWALS_ON_HOLD)
        return False
    return True


def test_s5_siblings_are_flagged_caps_stay_separate_and_withdrawals_wait(db, siblings, make_user):
    older, younger = siblings
    (flag,) = _suspected(db)
    assert (flag.score, flag.reasons, flag.status) == (60, ["device_id", "ip"], LinkFlagStatus.open)
    assert older.profile_group_id != younger.profile_group_id
    assert not _can_withdraw(db, older)
    assert not _can_withdraw(db, younger)

    dismiss(flag.id, make_user(UserRole.admin), db)  # admin: "Different people"
    assert flag.status == LinkFlagStatus.dismissed
    assert _can_withdraw(db, older) and _can_withdraw(db, younger)
    assert older.profile_group_id != younger.profile_group_id


def test_s5_confirmed_siblings_share_one_cap(db, siblings, make_user):
    older, younger = siblings
    (flag,) = _suspected(db)

    confirm(flag.id, make_user(UserRole.admin), db)  # admin: "Same person: merge caps"

    db.refresh(older)
    db.refresh(younger)
    assert flag.status == LinkFlagStatus.confirmed
    assert older.profile_group_id == younger.profile_group_id == older.id
    assert _can_withdraw(db, older)
