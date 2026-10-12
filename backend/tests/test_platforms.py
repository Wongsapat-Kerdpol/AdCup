"""[PERSON 3] services/platforms + routers/platforms — the layer every video platform plugs into.

Route functions are called directly, like test_submissions_api.py does."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models.connected_account import ConnectedAccount
from app.models.submission import SubmissionStatus
from app.models.user import UserRole
from app.routers.platforms import list_platforms, refresh_submission
from app.routers.submissions import create_submission
from app.schemas.submission import SubmissionCreate
from app.services import platforms
from app.services.platforms.base import VideoStats
from app.services.verification import run_system_check


def test_detect_youtube_links():
    for url in [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ]:
        adapter, video_id = platforms.detect(url)
        assert adapter.name == "youtube"
        assert video_id == "dQw4w9WgXcQ"


def test_detect_unknown_link():
    assert platforms.detect("https://example.com/video/123") is None


def test_youtube_rejection_message_unchanged(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    """The refactor must keep YouTube's wording (the frontend and Person 2's tests rely on it)."""
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda vid: video_info_factory(channel_id="someone-else"))
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    submission = make_submission(make_campaign(), creator)

    run_system_check(db, submission)

    assert submission.rejection_reason == "Video does not belong to your connected YouTube channel"


def test_campaign_must_accept_the_platform(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda vid: video_info_factory())
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    campaign = make_campaign(platforms=["tiktok"])
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "doesn't accept YouTube" in submission.rejection_reason


def test_submit_rejects_platform_the_campaign_does_not_accept(db, make_campaign, make_user):
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    campaign = make_campaign(platforms=["instagram"])

    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=campaign.id, video_url="https://youtu.be/xyz12345678"), creator, db)
    assert exc.value.status_code == 400
    assert "doesn't accept YouTube" in exc.value.detail


def test_submit_unrecognised_link(db, make_campaign, make_user):
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")

    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=make_campaign().id, video_url="https://example.com/v/1"), creator, db)
    assert exc.value.status_code == 400
    assert "Could not recognize" in exc.value.detail


# --- A platform whose stats need the creator's own login (how TikTok / Instagram will work) ---


class TokenPlatform:
    name = "tokenplat"
    label = "TokenPlat"
    account_label = "TokenPlat account"
    stats_need_user_token = True

    def __init__(self):
        self.accounts: dict[int, str] = {}
        self.fetches = 0

    def extract_video_id(self, url):
        return url.rsplit("/", 1)[-1] if url.startswith("https://tokenplat.test/") else None

    def connected_account_id(self, db, creator):
        return self.accounts.get(creator.id)

    def connected_account_name(self, db, creator):
        return "@tester" if creator.id in self.accounts else None

    def fetch_video(self, db, creator, video_id):
        self.fetches += 1
        return VideoStats(video_id, self.accounts[creator.id], "Clip", datetime.now(timezone.utc), 5000, True)


@pytest.fixture()
def token_platform(monkeypatch):
    plat = TokenPlatform()
    monkeypatch.setitem(platforms.ADAPTERS, plat.name, plat)
    supported = ("youtube", plat.name)
    for module in ("app.core.config", "app.services.platforms", "app.services.verification", "app.routers.submissions", "app.routers.platforms"):
        monkeypatch.setattr(f"{module}.SUPPORTED_SUBMISSION_PLATFORMS", supported)
    return plat


def test_token_platform_without_login_is_rejected_without_calling_the_api(db, make_campaign, make_user, make_submission, token_platform):
    creator = make_user(UserRole.creator)
    campaign = make_campaign(platforms=["tokenplat"])
    submission = make_submission(campaign, creator, platform="tokenplat", external_video_id="777")

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "connected TokenPlat account" in submission.rejection_reason
    assert token_platform.fetches == 0


def test_token_platform_end_to_end_submit(db, make_campaign, make_user, token_platform):
    creator = make_user(UserRole.creator)
    token_platform.accounts[creator.id] = "acct-9"
    campaign = make_campaign(platforms=["tokenplat"])

    submission = create_submission(
        SubmissionCreate(campaign_id=campaign.id, video_url="https://tokenplat.test/v/777"), creator, db
    )

    assert submission.platform == "tokenplat"
    assert submission.external_video_id == "777"
    assert submission.status == SubmissionStatus.under_review
    assert submission.video_channel_id == "acct-9"


def test_list_platforms_shows_connection_state(db, make_user, token_platform):
    creator = make_user(UserRole.creator, youtube_channel_id="UC1", youtube_channel_title="My Channel")

    result = {p.name: p for p in list_platforms(creator, db)}

    assert result["youtube"].connected and result["youtube"].account_name == "My Channel"
    assert result["youtube"].supported
    assert not result["tokenplat"].connected


def test_refresh_goes_through_the_adapter(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda vid: video_info_factory(video_id=vid, view_count=4321))
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    submission = make_submission(make_campaign(), creator, status=SubmissionStatus.approved)

    result = refresh_submission(submission.id, creator, db)

    assert result.view_count == 4321 and result.video_found


def test_old_youtube_refresh_paths_still_registered():
    paths = {getattr(r, "path", None): getattr(r, "endpoint", None) for r in app.routes}
    assert paths["/api/youtube/refresh/{submission_id}"] is refresh_submission
    assert "/api/youtube/refresh-all" in paths and "/api/platforms/refresh-all" in paths


def test_one_platform_account_per_user(db, make_user):
    a, b = make_user(UserRole.creator), make_user(UserRole.creator)
    db.add(ConnectedAccount(user_id=a.id, platform="tiktok", account_id="tt-1", access_token="x"))
    db.flush()
    db.add(ConnectedAccount(user_id=b.id, platform="tiktok", account_id="tt-1", access_token="y"))
    with pytest.raises(IntegrityError):
        db.flush()
