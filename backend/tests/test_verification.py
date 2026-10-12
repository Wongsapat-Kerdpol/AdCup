"""[PERSON 2] Round-1 automatic system check tests — the 6 ordered conditions."""

from datetime import datetime, timedelta, timezone

from app.models.submission import RejectedBy, SubmissionStatus
from app.models.user import UserRole
from app.services.verification import run_system_check


def _connect_channel(creator, channel_id: str = "channel-1"):
    creator.youtube_channel_id = channel_id
    creator.youtube_channel_title = "Test Channel"


def test_rejects_unsupported_platform(db, make_campaign, make_user, make_submission):
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(campaign, creator, platform="vimeo")  # not a platform AdCup supports

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert submission.rejected_by == RejectedBy.system
    assert "not supported" in submission.rejection_reason


def test_rejects_when_video_not_found(db, make_campaign, make_user, make_submission, monkeypatch):
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: None)
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "not found" in submission.rejection_reason


def test_rejects_when_not_public(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    info = video_info_factory(is_public=False)
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "not public" in submission.rejection_reason
    # video data is stored even though the submission was rejected
    assert submission.video_title == info.title


def test_rejects_wrong_channel(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    info = video_info_factory(channel_id="someone-elses-channel")
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    creator = make_user(UserRole.creator)
    _connect_channel(creator, "channel-1")
    campaign = make_campaign()
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "connected YouTube channel" in submission.rejection_reason


def test_rejects_when_no_channel_connected(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    info = video_info_factory(channel_id="channel-1")
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    creator = make_user(UserRole.creator)  # youtube_channel_id left unset
    campaign = make_campaign()
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "connected YouTube channel" in submission.rejection_reason


def test_rejects_published_before_campaign_start(
    db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory
):
    creator = make_user(UserRole.creator)
    _connect_channel(creator)
    campaign = make_campaign()  # funded "now"
    info = video_info_factory(channel_id="channel-1", published_at=datetime.now(timezone.utc) - timedelta(days=10))
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "before the campaign started" in submission.rejection_reason


def test_rejects_duplicate_submission_in_same_campaign(
    db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory
):
    creator = make_user(UserRole.creator)
    _connect_channel(creator)
    campaign = make_campaign()
    info = video_info_factory(channel_id="channel-1")
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)

    make_submission(campaign, creator, external_video_id="dup-video", status=SubmissionStatus.under_review)
    submission = make_submission(campaign, creator, external_video_id="dup-video")

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "already submitted" in submission.rejection_reason


def test_stays_pending_when_views_below_minimum(
    db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory
):
    creator = make_user(UserRole.creator)
    _connect_channel(creator)
    campaign = make_campaign(min_views=1000)
    info = video_info_factory(channel_id="channel-1", view_count=500)
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.pending  # unchanged, not rejected
    assert submission.rejection_reason is None
    assert submission.system_checked_at is not None
    assert submission.view_count == 500  # still recorded for the admin/creator to see


def test_passes_to_under_review_when_all_checks_pass(
    db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory
):
    creator = make_user(UserRole.creator)
    _connect_channel(creator)
    campaign = make_campaign(min_views=1000)
    info = video_info_factory(channel_id="channel-1", view_count=5000)
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.under_review
    assert submission.system_checked_at is not None
    assert submission.view_count == 5000


def test_rejects_when_deadline_passed_and_views_still_low(
    db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory
):
    creator = make_user(UserRole.creator)
    _connect_channel(creator)
    campaign = make_campaign(min_views=1000, deadline=datetime.now(timezone.utc) - timedelta(days=1))
    info = video_info_factory(channel_id="channel-1", view_count=500)
    monkeypatch.setattr("app.services.youtube.get_video_info", lambda video_id: info)
    submission = make_submission(campaign, creator)

    run_system_check(db, submission)

    assert submission.status == SubmissionStatus.rejected
    assert "minimum views" in submission.rejection_reason
