"""[PERSON 3] YouTube Data API access. Person 2 calls get_video_info() for the round-1 system check.

Contract (keep these signatures so Person 2 can code against them now):
    extract_video_id(url) -> str | None           # done (Main)
    get_video_info(video_id) -> VideoInfo | None  # done (Person 3) — needs YOUTUBE_API_KEY in .env
    refresh_views(db, submission) -> VideoInfo | None  # done (Person 3)

OAuth (done, Person 3) proves channel ownership: build_auth_url -> exchange_code -> get_my_channel.

refresh_views stores the fresh stats on the submission, then:
    - status pending  -> services.verification.run_system_check(db, submission)
    - status approved -> nothing more: money is only paid in payout rounds (services.payout.settle_*),
                         so refreshing earlier or more often gives no advantage.
The system check is looked up at call time, so refresh works (views only) before it lands.
Triggers: POST /api/youtube/refresh/{submission_id} and POST /api/youtube/refresh-all (routers/youtube.py).
"""

import importlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.submission import Submission, SubmissionStatus

log = logging.getLogger(__name__)

_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
# openid: the token response then carries an id_token with the Google account id ("sub"),
# a strong signal for linked account detection (services/identity.py).
_YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
_SCOPE = f"openid {_YOUTUBE_SCOPE}"

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


# --- Views refresh (hand-off to Person 2) ---


def _person2_step(module: str, name: str):
    """Person 2's function if it exists yet, else None (logged once per call)."""
    fn = getattr(importlib.import_module(f"app.services.{module}"), name, None)
    if fn is None:
        log.warning("services.%s.%s is not implemented yet (Person 2) — views refreshed only", module, name)
    return fn


def refresh_views(db: Session, submission: Submission) -> VideoInfo | None:
    """Pull fresh YouTube stats onto the submission, then run the next step of its lifecycle.

    Returns the VideoInfo, or None when the video no longer exists / is private (the stored
    stats are kept; for a pending submission the system check decides what that means).
    Raises httpx.HTTPError / RuntimeError on API or config problems, without saving anything.
    """
    video_id = submission.external_video_id or extract_video_id(submission.video_url)
    info = get_video_info(video_id) if video_id else None

    submission.views_refreshed_at = datetime.now(timezone.utc)
    if info is not None:
        submission.external_video_id = info.video_id
        submission.video_title = info.title[:300]
        submission.video_channel_id = info.channel_id
        submission.video_published_at = info.published_at
        submission.view_count = info.view_count
    db.flush()

    step = None
    if submission.status == SubmissionStatus.pending:
        step = _person2_step("verification", "run_system_check")
    if step is not None:
        step(db, submission)

    db.commit()
    return info


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


def google_sub_from(tokens: dict) -> str | None:
    """Google account id ("sub") from exchange_code()'s id_token, or None if there is none.

    The signature isn't checked: the token came straight from Google's token endpoint over TLS, which
    OpenID Connect allows instead of validating it (Core 1.0, section 3.1.3.7).
    """
    try:
        claims = jwt.decode(tokens.get("id_token", ""), options={"verify_signature": False})
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    return str(sub) if sub else None


def has_youtube_scope(tokens: dict) -> bool:
    """Asking for more than one scope makes Google show a checkbox per scope, so the user may grant
    openid but not YouTube. The token response lists what was actually granted."""
    return _YOUTUBE_SCOPE in tokens.get("scope", "").split()


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
