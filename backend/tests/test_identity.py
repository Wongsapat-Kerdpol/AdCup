"""Linked account detection, Phase 1 — normalizing, hashing and recording identity signals
(services/identity.py and the routes that collect them). See docs/linked-account-detection-spec.md."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.core.config import settings
from app.models.identity import IdentitySignal, SignalType
from app.models.user import UserRole
from app.routers.auth import login, register
from app.routers.payments import withdraw
from app.routers.submissions import create_submission
from app.routers.youtube import callback
from app.schemas.payment import WithdrawRequest
from app.schemas.submission import SubmissionCreate
from app.schemas.user import LoginRequest, RegisterRequest
from app.services import identity
from app.services import youtube as yt

DEVICE = "6f1c2b9e-1d2a-4c3b-8e4f-5a6b7c8d9e0f"


def _request(device_id: str | None = DEVICE, ip: str | None = "203.0.113.7") -> Request:
    headers = [(b"x-device-id", device_id.encode())] if device_id is not None else []
    return Request(
        {"type": "http", "method": "POST", "path": "/", "headers": headers, "client": (ip, 50000) if ip else None}
    )


def _signals(db, user) -> dict[SignalType, list[str]]:
    rows = db.scalars(select(IdentitySignal).where(IdentitySignal.user_id == user.id)).all()
    found: dict[SignalType, list[str]] = {}
    for row in rows:
        found.setdefault(row.type, []).append(row.value_hash)
    return found


# --- normalize ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("T.O.N+shorts@gmail.com", "ton@gmail.com"),
        ("a.b@googlemail.com", "ab@gmail.com"),
        ("a.b+x@hotmail.com", "a.b+x@hotmail.com"),
        ("  Mint@Example.COM ", "mint@example.com"),
    ],
)
def test_normalize_email(raw, expected):
    assert identity.normalize_email(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("081-234-5678", "+66812345678"),
        ("+66 81 234 5678", "+66812345678"),
        ("1-2345-67890-12-3", "1234567890123"),
    ],
)
def test_normalize_promptpay(raw, expected):
    assert identity.normalize_promptpay(raw) == expected


@pytest.mark.parametrize("raw", ["12345", "1812345678", ""])
def test_normalize_promptpay_rejects_other_lengths(raw):
    with pytest.raises(ValueError):
        identity.normalize_promptpay(raw)


def test_normalize_bank_account():
    assert identity.normalize_bank_account(" kbank", "123-4-56789-0") == "KBANK:1234567890"


# --- HMAC ---


def test_hash_is_stable_and_depends_on_the_type():
    a = identity.hash_signal(SignalType.email_norm, "ton@gmail.com")
    assert a == identity.hash_signal(SignalType.email_norm, "ton@gmail.com")
    assert a != identity.hash_signal(SignalType.google_sub, "ton@gmail.com")
    assert len(a) == 64 and "ton" not in a


def test_hash_depends_on_the_secret(monkeypatch):
    before = identity.hash_signal(SignalType.ip, "203.0.113.7")
    monkeypatch.setattr(settings, "identity_hash_secret", "another-secret")
    assert identity.hash_signal(SignalType.ip, "203.0.113.7") != before


# --- record_signal ---


def test_record_signal_upserts_one_row(db, make_user):
    creator = make_user(UserRole.creator)

    assert identity.record_signal(db, creator, SignalType.ip, "203.0.113.7") is True
    assert identity.record_signal(db, creator, SignalType.ip, "203.0.113.7") is False
    assert identity.record_signal(db, creator, SignalType.ip, "198.51.100.1") is True
    assert len(_signals(db, creator)[SignalType.ip]) == 2


def test_record_signal_skips_non_creators_and_empty_values(db, make_user):
    brand = make_user(UserRole.brand)
    creator = make_user(UserRole.creator)

    assert identity.record_signal(db, brand, SignalType.ip, "203.0.113.7") is False
    assert identity.record_signal(db, creator, SignalType.ip, None) is False
    assert _signals(db, brand) == {} and _signals(db, creator) == {}


def test_device_id_must_be_a_uuid():
    assert identity.device_id_from(_request(DEVICE.upper())) == DEVICE
    assert identity.device_id_from(_request("not-a-uuid")) is None
    assert identity.device_id_from(_request(None)) is None
    assert identity.device_id_from(None) is None


# --- collection points ---


def test_register_records_email_device_and_ip(db):
    body = RegisterRequest(display_name="Ton Shorts", email="T.O.N+shorts@gmail.com", password="password123", role=UserRole.creator)
    user = register(body, db, request=_request()).user

    found = _signals(db, user)
    assert set(found) == {SignalType.email_norm, SignalType.device_id, SignalType.ip}
    assert found[SignalType.email_norm] == [identity.hash_signal(SignalType.email_norm, "ton@gmail.com")]
    assert found[SignalType.device_id] == [identity.hash_signal(SignalType.device_id, DEVICE)]


def test_register_brand_records_nothing(db):
    body = RegisterRequest(display_name="Some Brand", email="brand@gmail.com", password="password123", role=UserRole.brand)
    user = register(body, db, request=_request()).user
    assert _signals(db, user) == {}


def test_register_without_a_request_still_records_the_email(db):
    body = RegisterRequest(display_name="Ton", email="ton@gmail.com", password="password123", role=UserRole.creator)
    user = register(body, db).user
    assert set(_signals(db, user)) == {SignalType.email_norm}


def test_login_records_device_and_ip(db, make_user):
    creator = make_user(UserRole.creator, email="mint@test.dev")
    login(LoginRequest(email="mint@test.dev", password="password123"), db, request=_request("bad-id"))
    assert set(_signals(db, creator)) == {SignalType.ip}  # a malformed device id is skipped, not an error


def test_submission_records_the_device_only(db, make_campaign, make_user, monkeypatch, video_info_factory):
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    campaign = make_campaign()
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: video_info_factory(channel_id="channel-1"))

    create_submission(SubmissionCreate(campaign_id=campaign.id, video_url="https://youtu.be/xyz12345678"), creator, db, request=_request())
    assert set(_signals(db, creator)) == {SignalType.device_id}


def test_withdraw_records_device_and_ip(db, make_user):
    creator = make_user(UserRole.creator, wallet_balance=Decimal("2000.00"))
    withdraw(WithdrawRequest(amount=Decimal("1500.00")), creator, db, request=_request())
    assert set(_signals(db, creator)) == {SignalType.device_id, SignalType.ip}


# --- Google account id (YouTube OAuth) ---


def test_google_sub_from_id_token():
    assert yt.google_sub_from({"id_token": jwt.encode({"sub": "1234567890"}, "k", algorithm="HS256")}) == "1234567890"
    assert yt.google_sub_from({"id_token": jwt.encode({"email": "x"}, "k", algorithm="HS256")}) is None
    assert yt.google_sub_from({"id_token": "garbage"}) is None
    assert yt.google_sub_from({}) is None


def test_scope_asks_for_openid():
    assert "openid" in yt._SCOPE.split()


def test_callback_records_google_sub_even_when_the_channel_is_taken(db, make_user, monkeypatch):
    make_user(UserRole.creator, youtube_channel_id="chan-1")  # owner of the channel
    other = make_user(UserRole.creator)
    state = jwt.encode(
        {"sub": str(other.id), "purpose": "youtube_connect", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    id_token = jwt.encode({"sub": "google-42"}, "k", algorithm="HS256")
    monkeypatch.setattr(yt, "exchange_code", lambda code: {"access_token": "a", "id_token": id_token})
    monkeypatch.setattr(yt, "get_my_channel", lambda token: yt.ChannelInfo(channel_id="chan-1", title="Taken"))

    response = callback(code="c", state=state, error=None, db=db)

    assert "channel_taken" in response.headers["location"]
    assert other.youtube_channel_id is None
    assert _signals(db, other)[SignalType.google_sub] == [identity.hash_signal(SignalType.google_sub, "google-42")]
