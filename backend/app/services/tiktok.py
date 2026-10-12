"""[PERSON 3] TikTok Login Kit + Display API (v2).

Unlike YouTube there is no API key for public stats: video.query only returns videos that belong
to the user whose access token we send. That also proves ownership — if TikTok returns the video
for the creator's token, it is theirs.

Tokens: access 24 h, refresh 365 d (TikTok may rotate the refresh token on every refresh).
Docs: developers.tiktok.com/doc/oauth-user-access-token-management, /tiktok-api-v2-video-query
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.platforms.base import PlatformError

_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
_VIDEO_QUERY_URL = "https://open.tiktokapis.com/v2/video/query/"
SCOPES = "user.info.basic,video.list"
_VIDEO_FIELDS = "id,create_time,title,video_description,view_count,share_url"

# https://www.tiktok.com/@user/video/7351234567890123456 (also /photo/ posts)
_ID_RE = re.compile(r"tiktok\.com/@[^/?#\s]+/(?:video|photo)/(\d{8,25})")
# Share links that redirect to the full URL: vm.tiktok.com/ZM..., vt.tiktok.com/..., tiktok.com/t/ZT...
_SHORT_RE = re.compile(r"^https?://(?:(?:vm|vt)\.tiktok\.com/|(?:www\.)?tiktok\.com/t/)[A-Za-z0-9]+")
# Token errors that mean "the creator must log in again" rather than "TikTok is down".
_AUTH_ERRORS = {"access_token_invalid", "scope_not_authorized", "invalid_grant", "invalid_token"}


class TikTokAuthError(PlatformError):
    """The creator's TikTok login is no longer valid — they need to reconnect."""


@dataclass
class TokenSet:
    open_id: str
    access_token: str
    access_expires_at: datetime
    refresh_token: str | None
    refresh_expires_at: datetime | None


@dataclass
class TikTokUser:
    open_id: str
    display_name: str


def extract_video_id(url: str) -> str | None:
    url = url.strip()
    if match := _ID_RE.search(url):
        return match.group(1)
    if _SHORT_RE.match(url):
        try:  # resolve the share link to the full /@user/video/<id> URL
            resp = httpx.get(url, follow_redirects=True, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        except httpx.HTTPError:
            return None
        if match := _ID_RE.search(str(resp.url)):
            return match.group(1)
    return None


def oauth_configured() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret and settings.tiktok_redirect_uri)


def build_auth_url(state: str) -> str:
    params = {
        "client_key": settings.tiktok_client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def _token_request(data: dict) -> TokenSet:
    resp = httpx.post(
        _TOKEN_URL,
        data={"client_key": settings.tiktok_client_key, "client_secret": settings.tiktok_client_secret, **data},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    body = resp.json() if resp.content else {}
    if body.get("error"):
        if body["error"] in _AUTH_ERRORS:
            raise TikTokAuthError("Your TikTok login expired — reconnect TikTok in Settings")
        raise httpx.HTTPStatusError(f"TikTok token error: {body['error']}", request=resp.request, response=resp)
    resp.raise_for_status()

    now = datetime.now(timezone.utc)
    refresh_in = body.get("refresh_expires_in")
    return TokenSet(
        open_id=body["open_id"],
        access_token=body["access_token"],
        access_expires_at=now + timedelta(seconds=int(body.get("expires_in", 86400))),
        refresh_token=body.get("refresh_token"),
        refresh_expires_at=now + timedelta(seconds=int(refresh_in)) if refresh_in else None,
    )


def exchange_code(code: str) -> TokenSet:
    return _token_request(
        {"code": code, "grant_type": "authorization_code", "redirect_uri": settings.tiktok_redirect_uri}
    )


def refresh_access_token(refresh_token: str) -> TokenSet:
    return _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})


def revoke(access_token: str) -> None:
    """Best effort — the account is unlinked locally even if TikTok is unreachable."""
    try:
        httpx.post(
            _REVOKE_URL,
            data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "token": access_token,
            },
            timeout=10,
        )
    except httpx.HTTPError:
        pass


def _api_get_data(resp: httpx.Response) -> dict:
    """TikTok v2 wraps results as {"data": ..., "error": {"code": "ok", ...}}."""
    body = resp.json() if resp.content else {}
    code = (body.get("error") or {}).get("code", "ok")
    if resp.status_code == 401 or code in _AUTH_ERRORS:
        raise TikTokAuthError("Your TikTok login expired — reconnect TikTok in Settings")
    if code != "ok":
        raise httpx.HTTPStatusError(f"TikTok API error: {code}", request=resp.request, response=resp)
    resp.raise_for_status()
    return body.get("data") or {}


def get_user(access_token: str) -> TikTokUser:
    resp = httpx.get(
        _USER_INFO_URL,
        params={"fields": "open_id,display_name"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    user = _api_get_data(resp).get("user", {})
    return TikTokUser(open_id=user["open_id"], display_name=user.get("display_name") or "")


def query_videos(access_token: str, video_ids: list[str]) -> dict[str, dict]:
    """{video_id: video} for the ids that belong to the token's user (max 20 per call)."""
    resp = httpx.post(
        _VIDEO_QUERY_URL,
        params={"fields": _VIDEO_FIELDS},
        json={"filters": {"video_ids": video_ids[:20]}},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    return {str(v["id"]): v for v in _api_get_data(resp).get("videos", [])}
