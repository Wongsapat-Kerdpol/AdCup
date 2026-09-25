"""[PERSON 3] Google OAuth + YouTube view refresh.

TODO(Person 3):
  GET  /api/youtube/connect                 — redirect to Google consent (scope: youtube.readonly)
  GET  /api/youtube/callback                — exchange code, channels.list?mine=true,
                                               save User.youtube_channel_id / _title / google_refresh_token
                                               (never return the token to the frontend)
  POST /api/youtube/disconnect              — clear those fields
  POST /api/youtube/refresh/{submission_id} — creator (owner) or admin: services.youtube.refresh_views()
  POST /api/youtube/refresh-all             — admin: refresh every pending + approved submission
                                               (approved ones in approved_at order -> FCFS payouts)
Config: settings.google_client_id / google_client_secret / google_redirect_uri
Google Cloud: enable "YouTube Data API v3", OAuth consent screen in Testing mode, add the team's
emails as test users (tokens of Testing-mode apps expire after 7 days — reconnect if needed).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/youtube", tags=["youtube (Person 3)"])
