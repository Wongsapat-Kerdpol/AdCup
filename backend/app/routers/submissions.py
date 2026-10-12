"""[PERSON 2] Content submission (creator side) + read-only views for brands.

  POST /api/submissions                   — creator submits a video link for a campaign
                                             (creator only; campaign must be active and accept that platform;
                                             creator must have connected their account on that platform
                                             and set up a payout account)
                                             -> platform + external_video_id detected from the link (services/platforms)
                                             -> save with status=pending, run services.verification.run_system_check()
  GET  /api/submissions/mine              — creator's submissions: status, rejection reason, views,
                                             gross / commission / net earned so far
  GET  /api/submissions/campaign/{id}     — brand owner of that campaign: READ-ONLY list
                                             (brands do not approve — admins do, see routers/review.py)

Lifecycle: pending (system check) -> under_review (admin) -> approved (earning) | rejected
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SUPPORTED_SUBMISSION_PLATFORMS
from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.submission import Submission as SubmissionSchema
from app.schemas.submission import SubmissionCreate
from app.services import platforms
from app.services.identity import record_request_signals
from app.services.link_review import capped_campaigns
from app.services.verification import run_system_check

router = APIRouter(prefix="/api/submissions", tags=["submissions (Person 2)"])

PAYOUT_ACCOUNT_REQUIRED = "Set up your payout account in Settings first"  # the frontend matches this text


@router.post("", response_model=SubmissionSchema)
def create_submission(
    body: SubmissionCreate,
    user: User = Depends(require_role(UserRole.creator)),
    db: Session = Depends(get_db),
    request: Request = None,
):
    campaign = db.get(Campaign, body.campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != CampaignStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not accepting submissions")
    detected = platforms.detect(body.video_url)
    if detected is None:
        labels = " or ".join(a.label for a in platforms.supported_adapters())
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not recognize that link — paste a {labels} video URL")
    adapter, video_id = detected
    if adapter.name not in SUPPORTED_SUBMISSION_PLATFORMS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{adapter.label} is not supported yet")
    if campaign.platforms and adapter.name not in campaign.platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"This campaign doesn't accept {adapter.label} videos"
        )
    if not adapter.connected_account_id(db, user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Connect your {adapter.account_label} in Settings first"
        )
    if user.payout_method is None:  # linked account detection, spec D8 (see routers/payout_method.py)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PAYOUT_ACCOUNT_REQUIRED)

    duplicate = db.scalar(
        select(Submission.id).where(
            Submission.campaign_id == campaign.id,
            Submission.platform == adapter.name,
            Submission.external_video_id == video_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already submitted to this campaign")

    submission = Submission(
        campaign_id=campaign.id,
        creator_id=user.id,
        video_url=body.video_url,
        platform=adapter.name,
        external_video_id=video_id,
        status=SubmissionStatus.pending,
    )
    db.add(submission)
    db.flush()
    # Linked account detection: device id only, before the system check so its risk score sees it.
    record_request_signals(db, user, request, ip=False)

    try:
        run_system_check(db, submission)
    except platforms.PlatformError as exc:  # e.g. their TikTok login expired — they can fix it
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not reach {adapter.label}, try again later"
        ) from exc

    db.commit()
    db.refresh(submission)
    return submission


@router.get("/mine", response_model=list[SubmissionSchema])
def my_submissions(user: User = Depends(require_role(UserRole.creator)), db: Session = Depends(get_db)):
    submissions = db.scalars(
        select(Submission).where(Submission.creator_id == user.id).order_by(Submission.created_at.desc())
    ).all()
    capped = capped_campaigns(db, user)  # linked account detection: shown as "Cap per profile reached"
    return [
        SubmissionSchema.model_validate(s).model_copy(
            update={"profile_cap_reached": s.status == SubmissionStatus.approved and s.campaign_id in capped}
        )
        for s in submissions
    ]


@router.get("/campaign/{campaign_id}", response_model=list[SubmissionSchema])
def submissions_for_campaign(
    campaign_id: int, user: User = Depends(require_role(UserRole.brand)), db: Session = Depends(get_db)
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.brand_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return db.scalars(
        select(Submission).where(Submission.campaign_id == campaign_id).order_by(Submission.created_at.desc())
    ).all()
