"""[PERSON 3] Admin analytics.

TODO(Person 3):
  GET /api/admin/stats — active users, transaction volume, commission revenue,
                         campaign performance. Guard with Depends(require_role(UserRole.admin)).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin (Person 3)"])
