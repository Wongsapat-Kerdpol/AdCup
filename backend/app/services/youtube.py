"""[PERSON 3] YouTube Data API access. Person 2 calls get_video_info() for the round-1 system check.

Contract (keep these signatures so Person 2 can code against them now):
    extract_video_id(url) -> str | None           # done (Main)
    get_video_info(video_id) -> VideoInfo | None  # done (Person 3) — needs YOUTUBE_API_KEY in .env
    refresh_views(db, submission)                 # moved to services/platforms (this name still works)

OAuth (done, Person 3) proves channel ownership: build_auth_url -> exchange_code -> get_my_channel.
The system check and views refresh reach YouTube through services/platforms/youtube.py.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.submission import Submission

_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"

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


# --- Views refresh ---


def refresh_views(db: Session, submission: Submission):
    """Kept for existing callers — the platform-agnostic version lives in services/platforms."""
    from app.services.platforms import refresh_views as refresh  # platforms imports this module

    return refresh(db, submission)


# --- Google OAuth (channel ownership) ---


@dataclass
class ChannelInfo:
    channel_id: str
    title: str


def oauth_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def build_auth_url(state: str) -> str:
    """Google consent page. offline + consent so Google always returns a refresh token."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Authorization code -> {"access_token", "refresh_token"?, ...}. Raises httpx.HTTPError."""
    resp = httpx.post(
        _TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_my_channel(access_token: str) -> ChannelInfo | None:
    """The signed-in Google account's YouTube channel, or None if it has no channel."""
    resp = httpx.get(
        _CHANNELS_URL,
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    return ChannelInfo(channel_id=items[0]["id"], title=items[0]["snippet"].get("title", ""))


def revoke_token(token: str) -> None:
    """Best effort — the channel is unlinked locally even if Google is unreachable."""
    try:
        httpx.post(_REVOKE_URL, data={"token": token}, timeout=10)
    except httpx.HTTPError:
        pass
