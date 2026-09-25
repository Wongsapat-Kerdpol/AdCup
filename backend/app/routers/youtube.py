"""[PERSON 3] Google OAuth + YouTube Data API.

TODO(Person 3):
  GET  /api/youtube/connect     — redirect to Google consent (scope: youtube.readonly)
  GET  /api/youtube/callback    — exchange code, store refresh token on User (never return it)
  POST /api/youtube/refresh/{submission_id} — pull real view_count for a submission
Config: settings.google_client_id / google_client_secret / google_redirect_uri
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/youtube", tags=["youtube (Person 3)"])
