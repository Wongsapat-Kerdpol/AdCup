"""[PERSON 2] routers/submissions.py — exercised by calling the route functions directly
(they're plain functions under the FastAPI decorators) rather than over HTTP, so tests don't
need to stand up the ASGI app / its lifespan against the dev database."""

import pytest
from fastapi import HTTPException

from app.models.campaign import CampaignStatus
from app.models.submission import SubmissionStatus
from app.models.user import UserRole
from app.routers.submissions import create_submission, my_submissions, submissions_for_campaign
from app.schemas.submission import SubmissionCreate

VALID_URL = "https://youtu.be/xyz12345678"


def _passing_video_info(video_info_factory, channel_id="channel-1"):
    return video_info_factory(channel_id=channel_id, view_count=5000)


def test_create_submission_success(db, make_campaign, make_user, monkeypatch, video_info_factory):
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    campaign = make_campaign()
    monkeypatch.setattr(
        "app.services.youtube.get_video_info", lambda video_id: _passing_video_info(video_info_factory)
    )

    submission = create_submission(SubmissionCreate(campaign_id=campaign.id, video_url=VALID_URL), creator, db)

    assert submission.status == SubmissionStatus.under_review
    assert submission.external_video_id == "xyz12345678"
    assert submission.creator_id == creator.id


def test_create_submission_requires_active_campaign(db, make_campaign, make_user):
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    campaign = make_campaign(fund=False)
    assert campaign.status == CampaignStatus.draft

    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=campaign.id, video_url=VALID_URL), creator, db)
    assert exc.value.status_code == 400


def test_create_submission_requires_youtube_channel(db, make_campaign, make_user):
    creator = make_user(UserRole.creator)  # no youtube_channel_id
    campaign = make_campaign()

    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=campaign.id, video_url=VALID_URL), creator, db)
    assert exc.value.status_code == 400


def test_create_submission_duplicate_is_conflict(db, make_campaign, make_user, make_submission, monkeypatch, video_info_factory):
    creator = make_user(UserRole.creator, youtube_channel_id="channel-1")
    campaign = make_campaign()
    make_submission(campaign, creator, external_video_id="xyz12345678")
    monkeypatch.setattr(
        "app.services.youtube.get_video_info", lambda video_id: _passing_video_info(video_info_factory)
    )

    with pytest.raises(HTTPException) as exc:
        create_submission(SubmissionCreate(campaign_id=campaign.id, video_url=VALID_URL), creator, db)
    assert exc.value.status_code == 409


def test_my_submissions_returns_only_own(db, make_campaign, make_user, make_submission):
    creator1 = make_user(UserRole.creator)
    creator2 = make_user(UserRole.creator)
    campaign = make_campaign()
    make_submission(campaign, creator1)
    make_submission(campaign, creator2)

    result = my_submissions(creator1, db)

    assert len(result) == 1
    assert result[0].creator_id == creator1.id


def test_submissions_for_campaign_requires_ownership(db, make_campaign, make_user):
    owner_brand = make_user(UserRole.brand)
    other_brand = make_user(UserRole.brand)
    campaign = make_campaign(brand=owner_brand)

    with pytest.raises(HTTPException) as exc:
        submissions_for_campaign(campaign.id, other_brand, db)
    assert exc.value.status_code == 404


def test_submissions_for_campaign_lists_for_owner(db, make_campaign, make_user, make_submission):
    owner_brand = make_user(UserRole.brand)
    campaign = make_campaign(brand=owner_brand)
    creator = make_user(UserRole.creator)
    make_submission(campaign, creator)

    result = submissions_for_campaign(campaign.id, owner_brand, db)

    assert len(result) == 1
