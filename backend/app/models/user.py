import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    brand = "brand"
    creator = "creator"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False, length=20))
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # In-app wallet (Person 3). Credited with net payouts, debited by withdrawals.
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))

    # YouTube linking (Person 3). OAuth tokens must never be sent to the frontend.
    youtube_channel_id: Mapped[str | None] = mapped_column(String(100))
    youtube_channel_title: Mapped[str | None] = mapped_column(String(255))
    google_refresh_token: Mapped[str | None] = mapped_column(String(1024))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
