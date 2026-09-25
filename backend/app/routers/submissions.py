"""[PERSON 2] Content submission (creator side) + read-only views for brands.

TODO(Person 2):
  POST /api/submissions                   — creator submits a YouTube link for a campaign
                                             (creator only; campaign must be active; must have connected YouTube)
                                             -> save with status=pending, external_video_id=extract_video_id(url)
                                             -> run services.verification.run_system_check()
  GET  /api/submissions/mine              — creator's submissions: status, rejection reason, views,
                                             gross / commission / net earned so far
  GET  /api/submissions/campaign/{id}     — brand owner of that campaign: READ-ONLY list
                                             (brands do not approve — admins do, see routers/review.py)

Lifecycle: pending (system check) -> under_review (admin) -> approved (earning) | rejected
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/submissions", tags=["submissions (Person 2)"])
