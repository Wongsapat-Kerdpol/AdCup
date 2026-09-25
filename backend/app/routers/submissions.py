"""[PERSON 2] Content submission + brand approval.

TODO(Person 2):
  POST /api/submissions                      — creator submits video_url for a campaign
  GET  /api/submissions/mine                 — creator's submissions + status
  GET  /api/campaigns/{id}/submissions       — brand sees submissions of own campaign
  POST /api/submissions/{id}/approve         — brand approves -> call services.payout.process_payout()
  POST /api/submissions/{id}/reject          — brand rejects with reason
Only `approved` submissions may ever produce a payout.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/submissions", tags=["submissions (Person 2)"])
