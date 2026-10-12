"""[ADMIN] Who submitted what — every submission of a campaign, with the creator, for admins.

  GET /api/admin/campaigns/{campaign_id}/submissions — all submissions of a campaign, every status,
                                                       newest first (shown on /campaigns/[id] to admins)
  GET /api/admin/submissions/{submission_id}         — full details incl. the creator's email

Brands keep their own read-only list (routers/submissions.py), without creator details.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign
from app.models.submission import Submission
from app.models.user import User, UserRole
from app.schemas.admin_submission import AdminSubmissionDetail, AdminSubmissionRow

router = APIRouter(prefix="/api/admin", tags=["admin: submissions"])


def _row(s: Submission, creator: User) -> dict:
    return dict(
        id=s.id,
        campaign_id=s.campaign_id,
        creator_id=creator.id,
        creator_name=creator.display_name,
        youtube_channel_id=creator.youtube_channel_id,
        youtube_channel_title=creator.youtube_channel_title,
        video_url=s.video_url,
        external_video_id=s.external_video_id,
        video_title=s.video_title,
        status=s.status,
        submitted_at=s.created_at,
        view_count=s.view_count,
        gross_amount=s.gross_amount,
        net_amount=s.net_amount,
    )


@router.get("/campaigns/{campaign_id}/submissions", response_model=list[AdminSubmissionRow])
def campaign_submissions(
    campaign_id: int, _: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)
):
    if db.get(Campaign, campaign_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    rows = db.execute(
        select(Submission, User)
        .join(User, User.id == Submission.creator_id)
        .where(Submission.campaign_id == campaign_id)
        .order_by(Submission.created_at.desc(), Submission.id.desc())
    ).all()
    return [AdminSubmissionRow(**_row(s, creator)) for s, creator in rows]


@router.get("/submissions/{submission_id}", response_model=AdminSubmissionDetail)
def submission_detail(
    submission_id: int, _: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)
):
    found = db.execute(
        select(Submission, User, Campaign.title)
        .join(User, User.id == Submission.creator_id)
        .join(Campaign, Campaign.id == Submission.campaign_id)
        .where(Submission.id == submission_id)
    ).first()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    s, creator, campaign_title = found
    count, net = db.execute(
        select(func.count(), func.coalesce(func.sum(Submission.net_amount), 0)).where(
            Submission.creator_id == creator.id
        )
    ).one()
    return AdminSubmissionDetail(
        **_row(s, creator),
        campaign_title=campaign_title,
        creator_email=creator.email,
        creator_joined_at=creator.created_at,
        creator_submissions=count,
        creator_net_earned=net,
        video_channel_id=s.video_channel_id,
        video_published_at=s.video_published_at,
        views_refreshed_at=s.views_refreshed_at,
        paid_views=s.paid_views,
        commission_amount=s.commission_amount,
        system_checked_at=s.system_checked_at,
        reviewed_at=s.reviewed_at,
        approved_at=s.approved_at,
        rejected_by=s.rejected_by,
        rejection_reason=s.rejection_reason,
    )
