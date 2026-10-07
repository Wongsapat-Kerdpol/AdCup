import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SubmissionStatus(str, enum.Enum):
    """Two-stage review (see README "Submission lifecycle").

    pending       -> round 1: automatic system check (ownership, public, published after
                     campaign start, views >= campaign.min_views). Stays here while views are too low.
    under_review  -> round 2: waiting for an admin to check the brand's content requirements.
    approved      -> admin passed it; earns money incrementally as views grow.
    rejected      -> failed round 1 (rejected_by="system") or round 2 (rejected_by="admin").
    """

    pending = "pending"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"


class RejectedBy(str, enum.Enum):
    system = "system"
    admin = "admin"


class Submission(Base):
    """One video submitted by a creator to a campaign (Person 2)."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    video_url: Mapped[str] = mapped_column(String(500))
    platform: Mapped[str] = mapped_column(String(20), default="youtube")  # YouTube only for now
    external_video_id: Mapped[str | None] = mapped_column(String(64))  # e.g. YouTube video id

    # Filled from the YouTube API (Person 3)
    video_title: Mapped[str | None] = mapped_column(String(300))
    video_channel_id: Mapped[str | None] = mapped_column(String(100))
    video_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(BigInteger, default=0)
    views_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, native_enum=False, length=20),
        default=SubmissionStatus.pending,
        index=True,
    )
    # Round 1 (system)
    system_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Round 2 (admin)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # approved_at: when the video joined the payout rounds (payouts don't depend on approval order).
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    rejected_by: Mapped[RejectedBy | None] = mapped_column(Enum(RejectedBy, native_enum=False, length=10))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # Running totals of everything paid for this submission so far (THB).
    # Each payout increment adds to these and writes one Transaction row.
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    paid_views: Mapped[int] = mapped_column(BigInteger, default=0)  # views already paid for

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
