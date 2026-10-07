"""[PERSON 2] routers/review.py — route functions called directly, same rationale as
test_submissions_api.py."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.submission import RejectedBy, SubmissionStatus
from app.models.user import UserRole
from app.routers.review import approve, reject, review_queue
from app.schemas.submission import RejectRequest
from app.services.payout import settle_campaign


def test_review_queue_lists_only_under_review(db, make_campaign, make_user, make_submission):
    admin = make_user(UserRole.admin)
    creator = make_user(UserRole.creator, display_name="Mint Creates")
    campaign = make_campaign(title="Water Bottle Promo", requirements="Show the bottle clearly")
    make_submission(campaign, creator, status=SubmissionStatus.pending)
    under_review = make_submission(campaign, creator, status=SubmissionStatus.under_review)
    make_submission(campaign, creator, status=SubmissionStatus.approved)

    result = review_queue(admin, db)

    assert [row.id for row in result] == [under_review.id]
    assert result[0].campaign_title == "Water Bottle Promo"
    assert result[0].campaign_requirements == "Show the bottle clearly"
    assert result[0].creator_name == "Mint Creates"


def test_approve_sets_fields_and_pays_in_the_next_round(db, make_campaign, make_user, make_submission):
    admin = make_user(UserRole.admin)
    creator = make_user(UserRole.creator)
    campaign = make_campaign(rate_per_1k_views=Decimal("1.00"))
    submission = make_submission(
        campaign, creator, status=SubmissionStatus.under_review, view_count=1000, paid_views=0
    )

    result = approve(submission.id, admin, db)

    assert result.status == SubmissionStatus.approved
    assert result.approved_at is not None
    assert result.reviewed_by_id == admin.id
    assert creator.wallet_balance == Decimal("0")  # approving never pays by itself

    settle_campaign(db, campaign.id)  # money moves in payout rounds
    assert creator.wallet_balance == Decimal("0.90")


def test_approve_requires_under_review_status(db, make_campaign, make_user, make_submission):
    admin = make_user(UserRole.admin)
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(campaign, creator, status=SubmissionStatus.pending)

    with pytest.raises(HTTPException) as exc:
        approve(submission.id, admin, db)
    assert exc.value.status_code == 409


def test_reject_sets_reason_and_rejected_by_admin(db, make_campaign, make_user, make_submission):
    admin = make_user(UserRole.admin)
    creator = make_user(UserRole.creator)
    campaign = make_campaign()
    submission = make_submission(campaign, creator, status=SubmissionStatus.under_review)

    result = reject(submission.id, RejectRequest(reason="Bottle not shown in the video"), admin, db)

    assert result.status == SubmissionStatus.rejected
    assert result.rejected_by == RejectedBy.admin
    assert result.rejection_reason == "Bottle not shown in the video"
    assert result.reviewed_by_id == admin.id
