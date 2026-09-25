"""[PERSON 3] YouTube Data API access. Person 2 calls get_video_info() for the round-1 system check.

Contract (keep these signatures so Person 2 can code against them now):
    extract_video_id(url) -> str | None           # done (Main)
    get_video_info(video_id) -> VideoInfo | None  # done (Person 3) — needs YOUTUBE_API_KEY in .env

TODO(Person 3):
  * OAuth is for proving channel ownership
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

import httpx

from app.core.config import settings

_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

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
    """Public metadata + view count via videos.list (API key only).

    Returns None if the video doesn't exist or is private (the API hides private videos from
    an API key). Unlisted videos are returned with is_public=False.
    Raises httpx.HTTPError on API/key/quota problems, so callers don't mistake an outage
    for "video not found" and reject a valid submission.
    """
    if not settings.youtube_api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not set (see .env.example)")

    resp = httpx.get(
        _VIDEOS_URL,
        params={"part": "snippet,statistics,status", "id": video_id, "key": settings.youtube_api_key},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None

    item = items[0]
    snippet = item["snippet"]
    return VideoInfo(
        video_id=item["id"],
        channel_id=snippet["channelId"],
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        tags=snippet.get("tags", []),
        published_at=datetime.fromisoformat(snippet["publishedAt"]),
        view_count=int(item.get("statistics", {}).get("viewCount", 0)),
        is_public=item.get("status", {}).get("privacyStatus") == "public",
    )
