"""[PERSON 3] Admin analytics.

TODO(Person 3):
  GET /api/admin/stats — active users, transaction volume, commission revenue,
                         campaign performance, submissions per status (pending/under_review/...).
                         Guard with Depends(require_role(UserRole.admin)).
(The admin submission review queue is Person 2's — see routers/review.py.)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin (Person 3)"])
