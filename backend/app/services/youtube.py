"""[PERSON 3] YouTube Data API access. Person 2 calls get_video_info() for the round-1 system check.

Contract (keep these signatures so Person 2 can code against them now):
    extract_video_id(url) -> str | None           # done (Main)
    get_video_info(video_id) -> VideoInfo | None  # TODO(Person 3)

TODO(Person 3):
  * get_video_info: GET https://www.googleapis.com/youtube/v3/videos
        ?part=snippet,statistics,status&id=<video_id>
    map -> VideoInfo. Return None if the video doesn't exist / is private.
    Public video stats only need an API key; OAuth is for proving channel ownership
    (channels.list?mine=true in the OAuth callback -> save User.youtube_channel_id).
  * refresh_views(db, submission): call get_video_info, update submission.view_count +
    views_refreshed_at, then hand over to Person 2:
        - status pending  -> services.verification.run_system_check(...)
        - status approved -> services.payout.process_payout(...)
  * Refresh triggers: a "Refresh views" button (POST /api/youtube/refresh/{submission_id})
    and optionally a periodic background job that refreshes all pending/approved submissions.
"""

import re
from dataclasses import dataclass
from datetime import datetime

_ID = r"([A-Za-z0-9_-]{11})"
_PATTERNS = [
    re.compile(rf"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/|v/))" + _ID),
    re.compile(rf"youtu\.be/" + _ID),
]


@dataclass
class VideoInfo:
    video_id: str
    channel_id: str
    title: str
    description: str
    tags: list[str]
    published_at: datetime
    view_count: int
    is_public: bool


def extract_video_id(url: str) -> str | None:
    """https://youtu.be/abc, youtube.com/watch?v=abc, /shorts/abc, /embed/abc -> 'abc' (11 chars)."""
    for pattern in _PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def get_video_info(video_id: str) -> VideoInfo | None:
    raise NotImplementedError("TODO(Person 3): call YouTube Data API v3 videos.list")
