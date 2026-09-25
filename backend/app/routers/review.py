"""[PERSON 2] Round 2 — admin review of the brand's content requirements.

Example: the brand requires "the water bottle must be visible in the video". The admin watches the
video and approves or rejects. Guard every endpoint with Depends(require_role(UserRole.admin)).

TODO(Person 2):
  GET  /api/admin/review                  — queue: submissions with status=under_review, oldest first,
                                             incl. campaign.requirements, video url/title, views, creator
  POST /api/admin/review/{id}/approve     — status=approved, approved_at=now, reviewed_by_id/at
                                             -> immediately services.payout.process_payout() for the
                                                views it already has
  POST /api/admin/review/{id}/reject      — body {reason}; status=rejected, rejected_by=admin
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/review", tags=["admin review (Person 2)"])
