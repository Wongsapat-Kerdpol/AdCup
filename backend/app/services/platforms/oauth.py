"""[PERSON 3] Shared bits of the "connect your account" OAuth round-trip, used by every platform router.

The state parameter is a short-lived JWT naming the user who started the flow and the platform,
so a callback can't be forged or replayed for another platform.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
from fastapi.responses import RedirectResponse

from app.core.config import settings

STATE_TTL = timedelta(minutes=10)


def make_state(user_id: int, platform: str) -> str:
    return jwt.encode(
        {"sub": str(user_id), "purpose": f"{platform}_connect", "exp": datetime.now(timezone.utc) + STATE_TTL},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def read_state(state: str, platform: str) -> int | None:
    """The user id inside a valid state for this platform, else None (forged / expired / other platform)."""
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != f"{platform}_connect":
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def settings_redirect(platform: str, result: str) -> RedirectResponse:
    """Back to the frontend's /settings page; it shows a toast for ?<platform>=<result>."""
    frontend = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    return RedirectResponse(f"{frontend}/settings?{urlencode({platform: result})}")
