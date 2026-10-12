"""All ORM models. Import from here so every table is registered on Base.metadata."""

from app.models.campaign import Campaign, CampaignCategory, CampaignStatus, Platform
from app.models.submission import RejectedBy, Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.models.video_hash import VideoHash

__all__ = [
    "Campaign",
    "CampaignCategory",
    "CampaignStatus",
    "Platform",
    "RejectedBy",
    "Submission",
    "SubmissionStatus",
    "Transaction",
    "TransactionStatus",
    "TransactionType",
    "User",
    "UserRole",
    "VideoHash",
]
