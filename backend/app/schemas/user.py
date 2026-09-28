from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


# --- Person 1: register / login ---

# Admins are created by hand (or the seed), never through the public sign-up form.
SignupRole = Literal[UserRole.brand, UserRole.creator]


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt only reads the first 72 bytes
    role: SignupRole

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Display name must be at least 2 characters")
        return v

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        # max_length counts characters; Thai/emoji are several bytes each, so check bytes too.
        if len(v.encode()) > 72:
            raise ValueError("Password is too long")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str
