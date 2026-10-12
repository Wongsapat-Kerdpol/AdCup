from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConnectedAccount(Base):
    """A creator's linked account on a platform whose stats need the creator's own OAuth token
    (TikTok). YouTube stays on User.youtube_* because its stats come from an API key.

    A new table, so `create_all` adds it to existing databases — no reset needed (Person 3).
    Tokens must never be sent to the frontend.
    """

    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_connected_account_user_platform"),
        # One platform account -> one AdCup user, otherwise two users could claim the same videos.
        UniqueConstraint("platform", "account_id", name="uq_connected_account_platform_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20))  # "tiktok"
    account_id: Mapped[str] = mapped_column(String(100))  # the platform's stable user id
    username: Mapped[str | None] = mapped_column(String(255))  # display only

    access_token: Mapped[str] = mapped_column(String(2048))
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_token: Mapped[str | None] = mapped_column(String(2048))
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
