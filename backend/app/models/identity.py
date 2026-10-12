"""Linked account detection — see docs/linked-account-detection-spec.md (sections 4 and 5).

identity_signals : what each creator account used (email, Google account, payout account, device, IP),
                   stored only as an HMAC hash. Strong signals put accounts in one profile group.
manual_links     : an admin confirmed that two accounts are the same person.
link_flags       : something for an admin to decide (suspected pair, shared "hub" value, overpaid group).
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignalType(str, enum.Enum):
    payout_account = "payout_account"  # strong: PromptPay / bank account the money goes to
    google_sub = "google_sub"  # strong: Google account id from the YouTube OAuth id_token
    email_norm = "email_norm"  # strong: email with Gmail dots / +tag removed
    device_id = "device_id"  # medium: random id the browser keeps in localStorage (risk score only)
    ip = "ip"  # weak: request IP (risk score only, never merges accounts)


class IdentitySignal(Base):
    __tablename__ = "identity_signals"
    __table_args__ = (
        UniqueConstraint("user_id", "type", "value_hash"),
        Index("ix_identity_signals_type_value_hash", "type", "value_hash"),  # "who else used this value?"
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[SignalType] = mapped_column(Enum(SignalType, native_enum=False, length=20))
    value_hash: Mapped[str] = mapped_column(String(64))  # HMAC-SHA256 hex of "type:normalized value"
    # Admin decided this value doesn't prove anything (e.g. an agency's Google account). Never for payout_account.
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualLinkKind(str, enum.Enum):
    confirmed_same = "confirmed_same"


class ManualLink(Base):
    __tablename__ = "manual_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[ManualLinkKind] = mapped_column(
        Enum(ManualLinkKind, native_enum=False, length=20), default=ManualLinkKind.confirmed_same
    )
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkFlagKind(str, enum.Enum):
    suspected = "suspected"  # weak signals scored >= the threshold; caps stay separate until an admin confirms
    hub = "hub"  # one strong value shared by more than MAX_SHARE accounts
    overage = "overage"  # a group was paid more than cap_per_profile before its accounts were linked


class LinkFlagStatus(str, enum.Enum):
    open = "open"  # withdrawals of everyone involved are on hold
    confirmed = "confirmed"
    dismissed = "dismissed"
    resolved = "resolved"


class LinkFlag(Base):
    __tablename__ = "link_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[LinkFlagKind] = mapped_column(Enum(LinkFlagKind, native_enum=False, length=20), index=True)
    user_a_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    user_b_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))
    # hub only: which shared value
    signal_type: Mapped[SignalType | None] = mapped_column(Enum(SignalType, native_enum=False, length=20))
    value_hash: Mapped[str | None] = mapped_column(String(64))
    score: Mapped[int | None] = mapped_column(Integer)  # suspected only
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # overage only: gross paid above the cap
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)  # e.g. ["device_id", "ip"]
    status: Mapped[LinkFlagStatus] = mapped_column(
        Enum(LinkFlagStatus, native_enum=False, length=20), default=LinkFlagStatus.open, index=True
    )
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
