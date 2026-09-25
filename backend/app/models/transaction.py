import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransactionType(str, enum.Enum):
    campaign_fund = "campaign_fund"  # brand deposits budget via mock checkout (Person 3)
    payout = "payout"  # one increment for an approved submission's new views (Person 2)
    withdrawal = "withdrawal"  # creator cash out (Person 3)


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Transaction(Base):
    """Money movement ledger. Every payout stores gross, commission (10%) and net."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), index=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("submissions.id"))

    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, native_enum=False, length=20))
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, native_enum=False, length=20), default=TransactionStatus.completed
    )
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference: Mapped[str | None] = mapped_column(String(100))  # e.g. mock checkout id
    # Payout only: which views this increment paid for (paid_views before -> view_count now).
    views_from: Mapped[int | None] = mapped_column(BigInteger)
    views_to: Mapped[int | None] = mapped_column(BigInteger)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
