"""[PERSON 2] Round 2 — admin review of the brand's content requirements.

Example: the brand requires "the water bottle must be visible in the video". The admin watches the
video and approves or rejects. Every endpoint is guarded with Depends(require_role(UserRole.admin)).

  GET  /api/admin/review                  — queue: submissions with status=under_review, oldest first,
                                             incl. campaign.requirements, video url/title, views, creator
  POST /api/admin/review/{id}/approve     — status=approved, approved_at=now, reviewed_by_id/at
                                             (earns from the next payout round — see services/payout.py)
  POST /api/admin/review/{id}/reject      — body {reason}; status=rejected, rejected_by=admin
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign
from app.models.submission import RejectedBy, Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.submission import RejectRequest
from app.schemas.submission import Submission as SubmissionSchema
from app.schemas.submission import SubmissionForReview

router = APIRouter(prefix="/api/admin/review", tags=["admin review (Person 2)"])


@router.get("", response_model=list[SubmissionForReview])
def review_queue(_: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Submission, Campaign.title, Campaign.requirements, User.display_name)
        .join(Campaign, Campaign.id == Submission.campaign_id)
        .join(User, User.id == Submission.creator_id)
        .where(Submission.status == SubmissionStatus.under_review)
        .order_by(Submission.system_checked_at.asc())
    ).all()
    return [
        SubmissionForReview.model_validate(submission).model_copy(
            update={"campaign_title": title, "campaign_requirements": requirements, "creator_name": creator_name}
        )
        for submission, title, requirements, creator_name in rows
    ]


def _get_under_review(db: Session, submission_id: int) -> Submission:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if submission.status != SubmissionStatus.under_review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Submission is not awaiting review")
    return submission


@router.post("/{submission_id}/approve", response_model=SubmissionSchema)
def approve(
    submission_id: int, user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)
):
    submission = _get_under_review(db, submission_id)

    submission.status = SubmissionStatus.approved
    submission.approved_at = datetime.now(timezone.utc)
    submission.reviewed_by_id = user.id
    submission.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(submission)
    return submission


@router.post("/{submission_id}/reject", response_model=SubmissionSchema)
def reject(
    submission_id: int,
    body: RejectRequest,
    user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    submission = _get_under_review(db, submission_id)

    submission.status = SubmissionStatus.rejected
    submission.rejected_by = RejectedBy.admin
    submission.rejection_reason = body.reason
    submission.reviewed_by_id = user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(submission)
    return submission
