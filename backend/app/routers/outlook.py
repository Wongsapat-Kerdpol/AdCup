"""Is this campaign still worth joining? (public — shown on the campaign page)

  GET /api/campaigns/{id}/outlook?views_per_day=N
      Projects how fast the pool will be claimed by already-approved videos, when it runs dry, and
      what a new video getting N views/day (default: the median of existing videos) could earn.
      See services/outlook.py.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.campaign import Campaign
from app.schemas.outlook import CampaignOutlook
from app.services.outlook import campaign_outlook

router = APIRouter(prefix="/api/campaigns", tags=["campaign outlook"])


@router.get("/{campaign_id}/outlook", response_model=CampaignOutlook)
def get_outlook(
    campaign_id: int,
    views_per_day: float | None = Query(None, ge=0, le=100_000_000),
    db: Session = Depends(get_db),
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignOutlook.model_validate(asdict(campaign_outlook(db, campaign, views_per_day)))
