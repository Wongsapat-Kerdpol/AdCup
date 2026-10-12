import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    brand = "brand"
    creator = "creator"
    admin = "admin"


class PayoutMethod(str, enum.Enum):
    promptpay = "promptpay"
    bank = "bank"


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

    # Linked account detection. Accounts of the same person share one cap per profile; the group id
    # is the smallest user id in the group (services/linking.py). Never sent to creators.
    profile_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # Payout account, display-only (masked). The full value is kept only as an HMAC in identity_signals.
    payout_method: Mapped[PayoutMethod | None] = mapped_column(Enum(PayoutMethod, native_enum=False, length=20))
    payout_bank_code: Mapped[str | None] = mapped_column(String(20))
    payout_account_masked: Mapped[str | None] = mapped_column(String(30))  # e.g. "••• 5678"
    payout_account_name: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
