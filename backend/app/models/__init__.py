"""All ORM models. Import from here so every table is registered on Base.metadata."""

from app.models.campaign import Campaign, CampaignCategory, CampaignStatus, Platform
from app.models.identity import (
    IdentitySignal,
    LinkFlag,
    LinkFlagKind,
    LinkFlagStatus,
    ManualLink,
    ManualLinkKind,
    SignalType,
)
from app.models.submission import RejectedBy, Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import PayoutMethod, User, UserRole

__all__ = [
    "Campaign",
    "CampaignCategory",
    "CampaignStatus",
    "IdentitySignal",
    "LinkFlag",
    "LinkFlagKind",
    "LinkFlagStatus",
    "ManualLink",
    "ManualLinkKind",
    "PayoutMethod",
    "Platform",
    "RejectedBy",
    "SignalType",
    "Submission",
    "SubmissionStatus",
    "Transaction",
    "TransactionStatus",
    "TransactionType",
    "User",
    "UserRole",
]
