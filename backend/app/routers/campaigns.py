"""[MAIN] Public campaign browsing used by the Discover page and the campaign card."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.campaign import Campaign, CampaignCategory, CampaignStatus
from app.models.user import User
from app.schemas.campaign import CampaignDetail, CampaignListResponse, CampaignSort

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    category: CampaignCategory | None = None,
    platform: str | None = Query(None, description="youtube | tiktok"),
    search: str | None = Query(None, max_length=100),
    sort: CampaignSort = CampaignSort.newest,
    status: CampaignStatus | None = Query(CampaignStatus.active),
    brand_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Campaign).join(Campaign.brand)

    if status is not None:
        stmt = stmt.where(Campaign.status == status)
    if category is not None:
        stmt = stmt.where(Campaign.category == category)
    if platform:
        stmt = stmt.where(Campaign.platforms.any(platform))
    if brand_id is not None:
        stmt = stmt.where(Campaign.brand_id == brand_id)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Campaign.title.ilike(pattern),
                Campaign.description.ilike(pattern),
                User.display_name.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    paid_ratio = Campaign.paid_out / func.nullif(Campaign.total_budget, 0)
    order_by = {
        CampaignSort.newest: [Campaign.created_at.desc()],
        CampaignSort.highest_rate: [Campaign.rate_per_1k_views.desc()],
        CampaignSort.highest_budget: [Campaign.total_budget.desc()],
        CampaignSort.most_available: [paid_ratio.asc()],
        CampaignSort.ending_soon: [Campaign.deadline.asc().nulls_last()],
    }[sort]
    stmt = stmt.order_by(*order_by, Campaign.id.desc())

    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return CampaignListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign
