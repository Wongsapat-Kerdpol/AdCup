import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Submission(Base):
    """One video submitted by a creator to a campaign (Person 2)."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    video_url: Mapped[str] = mapped_column(String(500))
    platform: Mapped[str] = mapped_column(String(20))
    youtube_video_id: Mapped[str | None] = mapped_column(String(32))
    view_count: Mapped[int] = mapped_column(BigInteger, default=0)  # refreshed from YouTube API

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, native_enum=False, length=20),
        default=SubmissionStatus.pending,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    # approved_at defines the first-come-first-served payout order.
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Filled by the payout engine; all THB.
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
