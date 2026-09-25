import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import DEFAULT_MIN_VIEWS
from app.core.database import Base
from app.models.user import User


class CampaignCategory(str, enum.Enum):
    logo = "logo"
    music = "music"
    clipping = "clipping"
    ugc = "ugc"


class CampaignStatus(str, enum.Enum):
    draft = "draft"  # created but not funded yet
    active = "active"  # funded and accepting submissions
    paused = "paused"
    completed = "completed"  # budget used up or deadline passed


class Platform(str, enum.Enum):
    # Only YouTube submissions are verified for now; TikTok/IG come later.
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"
    x = "x"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")  # content rules
    category: Mapped[CampaignCategory] = mapped_column(
        Enum(CampaignCategory, native_enum=False, length=20), index=True
    )
    platforms: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))

    # Money is always THB. The rate is stored per 1,000 views (proposal);
    # the UI shows it per 1M views (x1000) like Clipster.
    rate_per_1k_views: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_budget: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Gross amount already paid out of the pool. Updated by the payout engine (Person 2).
    paid_out: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    cap_per_post: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # max gross per submission
    cap_per_profile: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # max gross per creator (this campaign)
    # Round-1 system check: a video needs at least this many views before it can go to admin review.
    min_views: Mapped[int] = mapped_column(Integer, default=DEFAULT_MIN_VIEWS)

    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, native_enum=False, length=20), default=CampaignStatus.draft, index=True
    )
    is_funded: Mapped[bool] = mapped_column(Boolean, default=False)  # set by mock checkout (Person 3)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped[User] = relationship(lazy="joined")

    @property
    def remaining_budget(self) -> Decimal:
        return max(self.total_budget - self.paid_out, Decimal("0"))

    @property
    def paid_out_percent(self) -> float:
        if not self.total_budget:
            return 0.0
        return round(float(self.paid_out / self.total_budget * 100), 1)

    @property
    def rate_per_1m_views(self) -> Decimal:
        return self.rate_per_1k_views * 1000
