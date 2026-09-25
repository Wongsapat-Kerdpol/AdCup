"""[PERSON 1] Brand campaign management.

TODO(Person 1):
  POST  /api/campaigns          — brand creates a campaign (status=draft, is_funded=False)
                                   use Depends(require_role(UserRole.brand))
                                   fields incl. requirements (checked by admin in round 2),
                                   min_views (default 1,000), cap_per_post, cap_per_profile
  PATCH /api/campaigns/{id}     — brand edits own campaign
  GET   /api/campaigns/mine     — brand's own campaigns incl. drafts
                                   (declare this route BEFORE /{campaign_id} or use a different path,
                                    e.g. /api/brand/campaigns, to avoid clashing with campaigns.py)
Read-only listing/detail already exists in routers/campaigns.py (Main).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/brand", tags=["campaign-manage (Person 1)"])
