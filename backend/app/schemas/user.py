from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserPublic(BaseModel):
    """Safe user representation. Never add password_hash or OAuth tokens here."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    wallet_balance: Decimal
    youtube_channel_id: str | None = None
    youtube_channel_title: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class DevLoginRequest(BaseModel):
    role: UserRole
