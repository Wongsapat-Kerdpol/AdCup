"""[PERSON 3] TikTok: link parsing, token refresh, adapter, system check, account linking.

Nothing here calls TikTok — every network function in services/tiktok.py is monkeypatched."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.connected_account import ConnectedAccount
from app.models.submission import SubmissionStatus
from app.models.user import UserRole
from app.routers import tiktok as tiktok_router
from app.routers.submissions import create_submission
from app.schemas.submission import SubmissionCreate
from app.services import tiktok as tt
from app.services.platforms import PlatformError, get_adapter
from app.services.platforms.oauth import make_state
from app.services.platforms.tiktok import valid_access_token
from app.services.verification import run_system_check

VIDEO_ID = "7351234567890123456"
VIDEO_URL = f"https://www.tiktok.com/@mint.creates/video/{VIDEO_ID}?is_from_webapp=1"
NOW = datetime.now(timezone.utc)


def _link(db, user, *, open_id="open-1", access_expires_at=None, refresh_expires_at=None):
    account = ConnectedAccount(
        user_id=user.id,
        platform="tiktok",
        account_id=open_id,
        username="Mint",
        access_token="access-old",
        access_expires_at=access_expires_at or NOW + timedelta(hours=12),
        refresh_token="refresh-old",
        refresh_expires_at=refresh_expires_at or NOW + timedelta(days=300),
    )
    db.add(account)
    db.flush()
    return account


def _video(**overrides):
    # Published a minute in the future so it's always after the test campaign's start.
    published = int((datetime.now(timezone.utc) + timedelta(minutes=1)).timestamp())
    return {"id": VIDEO_ID, "create_time": published, "title": "My promo", "view_count": 4200, **overrides}


@pytest.fixture()
def tiktok_api(monkeypatch):
    """Fake TikTok: records calls, returns whatever the test puts in `videos`."""
    api = SimpleNamespace(videos={VIDEO_ID: _video()}, tokens_used=[], refreshed=0)

    def query_videos(token, ids):
        api.tokens_used.append(token)
        return {i: api.videos[i] for i in ids if i in api.videos}

    def refresh_access_token(refresh_token):
        api.refreshed += 1
        return tt.TokenSet("open-1", "access-new", NOW + timedelta(hours=24), "refresh-new", NOW + timedelta(days=365))

    monkeypatch.setattr(tt, "query_videos", query_videos)
    monkeypatch.setattr(tt, "refresh_access_token", refresh_access_token)
    return api


# --- link parsing ---


@pytest.mark.parametrize(
    "url",
    [VIDEO_URL, f"https://tiktok.com/@a.b_c/video/{VIDEO_ID}", f"https://www.tiktok.com/@x/photo/{VIDEO_ID}"],
)
def test_extract_full_links(url):
    assert tt.extract_video_id(url) == VIDEO_ID


def test_extract_short_link_follows_redirect(monkeypatch):
    monkeypatch.setattr(tt.httpx, "get", lambda url, **kw: SimpleNamespace(url=f"https://www.tiktok.com/@m/video/{VIDEO_ID}"))
    assert tt.extract_video_id("https://vm.tiktok.com/ZMabc123/") == VIDEO_ID


def test_extract_rejects_other_links():
    assert tt.extract_video_id("https://youtu.be/dQw4w9WgXcQ") is None
    assert tt.extract_video_id("https://www.tiktok.com/@mint.creates") is None


# --- token handling ---


def test_fresh_token_is_used_as_is(db, make_user, tiktok_api):
    account = _link(db, make_user())
    assert valid_access_token(db, account) == "access-old"
    assert tiktok_api.refreshed == 0


def test_expiring_token_is_refreshed_and_rotated(db, make_user, tiktok_api):
    account = _link(db, make_user(), access_expires_at=NOW + timedelta(minutes=2))

    assert valid_access_token(db, account) == "access-new"
    assert account.refresh_token == "refresh-new"  # TikTok rotated it; the old one is dead
    assert tiktok_api.refreshed == 1


def test_expired_refresh_token_asks_to_reconnect(db, make_user, tiktok_api):
    account = _link(db, make_user(), access_expires_at=NOW - timedelta(hours=1), refresh_expires_at=NOW - timedelta(days=1))
    with pytest.raises(PlatformError, match="reconnect TikTok"):
        valid_access_token(db, account)


# --- adapter + system check ---


def test_adapter_maps_video_fields(db, make_user, tiktok_api):
    creator = make_user()
    _link(db, creator)

    stats = get_adapter("tiktok").fetch_video(db, creator, VIDEO_ID)

    assert (stats.video_id, stats.owner_id, stats.title, stats.view_count, stats.is_public) == (VIDEO_ID, "open-1", "My promo", 4200, True)
    assert tiktok_api.tokens_used == ["access-old"]


def test_system_check_passes_own_video(db, make_campaign, make_user, make_submission, tiktok_api):
    creator = make_user()
    _link(db, creator)
    submission = make_submission(make_campaign(platforms=["tiktok"]), creator, platform="tiktok", external_video_id=VIDEO_ID)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.under_review, submission.rejection_reason
    assert submission.view_count == 4200


def test_system_check_rejects_video_not_on_their_account(db, make_campaign, make_user, make_submission, tiktok_api):
    creator = make_user()
    _link(db, creator)
    tiktok_api.videos = {}  # TikTok doesn't return it for this creator's token
    submission = make_submission(make_campaign(platforms=["tiktok"]), creator, platform="tiktok", external_video_id=VIDEO_ID)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "connected TikTok account" in submission.rejection_reason


def test_system_check_waits_for_min_views(db, make_campaign, make_user, make_submission, tiktok_api):
    creator = make_user()
    _link(db, creator)
    tiktok_api.videos[VIDEO_ID] = _video(view_count=300)
    submission = make_submission(make_campaign(platforms=["tiktok"]), creator, platform="tiktok", external_video_id=VIDEO_ID)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.pending


def test_submit_tiktok_link_end_to_end(db, make_campaign, make_user, tiktok_api):
    creator = make_user()
    _link(db, creator)
    campaign = make_campaign(platforms=["youtube", "tiktok"])

    submission = create_submission(SubmissionCreate(campaign_id=campaign.id, video_url=VIDEO_URL), creator, db)

    assert (submission.platform, submission.external_video_id, submission.status) == ("tiktok", VIDEO_ID, SubmissionStatus.under_review)


def test_submit_tiktok_requires_linked_account(db, make_campaign, make_user):
    creator = make_user(youtube_channel_id="UC1")  # YouTube alone isn't enough for a TikTok link
    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=make_campaign(platforms=["tiktok"]).id, video_url=VIDEO_URL), creator, db)
    assert exc.value.status_code == 400
    assert "Connect your TikTok account" in exc.value.detail


def test_submit_with_revoked_login_is_400_not_502(db, make_campaign, make_user, monkeypatch):
    creator = make_user()
    _link(db, creator)

    def revoked(token, ids):
        raise tt.TikTokAuthError("Your TikTok login expired — reconnect TikTok in Settings")

    monkeypatch.setattr(tt, "query_videos", revoked)
    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=make_campaign(platforms=["tiktok"]).id, video_url=VIDEO_URL), creator, db)
    assert exc.value.status_code == 400
    assert "reconnect TikTok" in exc.value.detail


# --- account linking ---


@pytest.fixture()
def tiktok_login(monkeypatch):
    monkeypatch.setattr(tt, "exchange_code", lambda code: tt.TokenSet("open-1", "at", NOW + timedelta(hours=24), "rt", NOW + timedelta(days=365)))
    monkeypatch.setattr(tt, "get_user", lambda token: tt.TikTokUser("open-1", "Mint"))


def _location(resp):
    return resp.headers["location"].rsplit("?", 1)[-1]


def test_callback_links_account(db, make_user, tiktok_login):
    creator = make_user()

    resp = tiktok_router.callback(code="c", state=make_state(creator.id, "tiktok"), error=None, db=db)

    assert _location(resp) == "tiktok=connected"
    account = db.query(ConnectedAccount).filter_by(user_id=creator.id, platform="tiktok").one()
    assert (account.account_id, account.username, account.refresh_token) == ("open-1", "Mint", "rt")


def test_callback_rejects_youtube_state_and_cancel(db, make_user, tiktok_login):
    creator = make_user()
    assert _location(tiktok_router.callback(code="c", state=make_state(creator.id, "youtube"), error=None, db=db)) == "tiktok=expired"
    assert _location(tiktok_router.callback(code=None, state=None, error="access_denied", db=db)) == "tiktok=denied"


def test_callback_one_tiktok_account_per_adcup_user(db, make_user, tiktok_login):
    first, second = make_user(), make_user()
    _link(db, first, open_id="open-1")

    resp = tiktok_router.callback(code="c", state=make_state(second.id, "tiktok"), error=None, db=db)

    assert _location(resp) == "tiktok=account_taken"


def test_disconnect_revokes_and_deletes(db, make_user, monkeypatch):
    creator = make_user()
    _link(db, creator)
    revoked = []
    monkeypatch.setattr(tt, "revoke", revoked.append)

    tiktok_router.disconnect(creator, db)

    assert revoked == ["access-old"]
    assert db.query(ConnectedAccount).filter_by(user_id=creator.id).count() == 0


def test_connect_without_config_is_503(make_user, monkeypatch):
    monkeypatch.setattr(tt, "oauth_configured", lambda: False)
    with pytest.raises(HTTPException) as exc:
        tiktok_router.connect(make_user(UserRole.creator))
    assert exc.value.status_code == 503
