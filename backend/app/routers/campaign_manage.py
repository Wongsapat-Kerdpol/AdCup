"""[PERSON 1] Brand campaign management.

  POST   /api/brand/campaigns        — brand creates a campaign (status=draft, is_funded=False);
                                        next step is the mock checkout at /campaigns/{id}/fund (Person 3)
  GET    /api/brand/campaigns        — brand's own campaigns incl. drafts, with submission stats
  PATCH  /api/brand/campaigns/{id}   — brand edits own campaign (money rules locked once funded)
  DELETE /api/brand/campaigns/{id}   — brand deletes an unfunded draft

Read-only listing/detail for everyone lives in routers/campaigns.py (Main).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.campaign import CampaignDetail
from app.schemas.campaign_manage import (
    BrandCampaign,
    BrandCampaignStats,
    CampaignCreate,
    CampaignUpdate,
)

router = APIRouter(prefix="/api/brand", tags=["campaign-manage (Person 1)"])

# Changing these after funding would change the deal creators signed up for.
LOCKED_WHEN_FUNDED = {"rate_per_1k_views", "total_budget", "cap_per_post", "cap_per_profile", "min_views"}


def _check_deadline(deadline: datetime | None) -> None:
    if deadline is not None and deadline <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Deadline must be in the future")


def _own_campaign(db: Session, campaign_id: int, user: User) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    # 404 (not 403) for other brands' campaigns so ids can't be probed.
    if campaign is None or campaign.brand_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.post("/campaigns", response_model=CampaignDetail, status_code=status.HTTP_201_CREATED)
def create_campaign(
    body: CampaignCreate,
    user: User = Depends(require_role(UserRole.brand)),
    db: Session = Depends(get_db),
):
    _check_deadline(body.deadline)
    campaign = Campaign(
        brand_id=user.id,
        **body.model_dump(exclude={"platforms"}),
        platforms=[p.value for p in body.platforms],
        status=CampaignStatus.draft,
        is_funded=False,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/campaigns", response_model=list[BrandCampaign])
def my_campaigns(user: User = Depends(require_role(UserRole.brand)), db: Session = Depends(get_db)):
    campaigns = db.scalars(
        select(Campaign).where(Campaign.brand_id == user.id).order_by(Campaign.created_at.desc(), Campaign.id.desc())
    ).all()
    ids = [c.id for c in campaigns]

    by_status: dict[int, dict[SubmissionStatus, int]] = {i: {s: 0 for s in SubmissionStatus} for i in ids}
    totals: dict[int, tuple[int, int]] = {}
    if ids:
        for campaign_id, sub_status, count in db.execute(
            select(Submission.campaign_id, Submission.status, func.count())
            .where(Submission.campaign_id.in_(ids))
            .group_by(Submission.campaign_id, Submission.status)
        ):
            by_status[campaign_id][sub_status] = count
        for campaign_id, creators, views in db.execute(
            select(
                Submission.campaign_id,
                func.count(distinct(Submission.creator_id)),
                func.coalesce(func.sum(Submission.view_count).filter(Submission.status == SubmissionStatus.approved), 0),
            )
            .where(Submission.campaign_id.in_(ids))
            .group_by(Submission.campaign_id)
        ):
            totals[campaign_id] = (creators, int(views))

    return [
        BrandCampaign(
            **CampaignDetail.model_validate(c).model_dump(),
            stats=BrandCampaignStats(
                submissions=by_status[c.id],
                creators=totals.get(c.id, (0, 0))[0],
                total_views=totals.get(c.id, (0, 0))[1],
            ),
        )
        for c in campaigns
    ]


@router.patch("/campaigns/{campaign_id}", response_model=CampaignDetail)
def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    user: User = Depends(require_role(UserRole.brand)),
    db: Session = Depends(get_db),
):
    campaign = _own_campaign(db, campaign_id, user)
    changes = body.model_dump(exclude_unset=True)

    if campaign.status == CampaignStatus.completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed campaigns can't be edited")
    if campaign.is_funded:
        locked = sorted(k for k in LOCKED_WHEN_FUNDED & changes.keys() if changes[k] != getattr(campaign, k))
        if locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Can't change {', '.join(locked)} after the campaign is funded",
            )
    new_status = changes.pop("status", None)
    if new_status is not None and not campaign.is_funded:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fund the campaign before activating it")
    if "deadline" in changes and changes["deadline"] != campaign.deadline:
        _check_deadline(changes["deadline"])

    # Re-validate the campaign as a whole with the same rules as create (caps vs budget, lengths, ...).
    # Platforms are only checked when changed: seeded campaigns list TikTok/IG, which the form can't pick.
    fields = set(CampaignCreate.model_fields) - {"platforms"}
    current = CampaignDetail.model_validate(campaign).model_dump(include=fields)
    try:
        merged = CampaignCreate.model_validate({**current, **changes})
    except ValidationError as exc:
        err = exc.errors()[0]
        field = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field}: {msg}" if field else msg
        ) from exc

    for key in changes:
        value = getattr(merged, key)
        setattr(campaign, key, [p.value for p in value] if key == "platforms" else value)
    if new_status is not None:
        campaign.status = new_status
    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: int,
    user: User = Depends(require_role(UserRole.brand)),
    db: Session = Depends(get_db),
):
    campaign = _own_campaign(db, campaign_id, user)
    if campaign.is_funded:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Funded campaigns can't be deleted")
    db.delete(campaign)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
