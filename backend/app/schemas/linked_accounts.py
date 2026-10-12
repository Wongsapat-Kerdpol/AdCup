"""Linked account detection — admin views. Signal VALUES are never included, only their types (spec D14)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.identity import LinkFlagKind, LinkFlagStatus, SignalType


class LinkedUser(BaseModel):
    id: int
    display_name: str


class LinkedAccount(BaseModel):
    """Review queue: another account of the same profile group that also submitted to this campaign."""

    user_id: int
    display_name: str
    matched: list[str]  # signal types they share directly, e.g. ["payout_account"]; "manual" = admin-confirmed


class OpenLinkFlag(BaseModel):
    """Review queue: an open suspected / overage flag of the submitter's group in this campaign."""

    id: int
    kind: LinkFlagKind
    reasons: list[str]
    score: int | None = None
    amount: Decimal | None = None
    other_user_id: int | None = None  # suspected: the other account of the pair
    other_display_name: str | None = None


class LinkFlagOut(BaseModel):
    id: int
    kind: LinkFlagKind
    status: LinkFlagStatus
    created_at: datetime
    # suspected: the pair · hub: every account using the value · overage: the profile group
    users: list[LinkedUser]
    reasons: list[str]
    score: int | None = None  # suspected
    signal_type: SignalType | None = None  # hub
    campaign_id: int | None = None
    campaign_title: str | None = None
    amount: Decimal | None = None  # overage: gross paid above the cap
    group_gross: Decimal | None = None  # overage: what the group has been paid in the campaign
    cap_per_profile: Decimal | None = None  # overage


class ProfileGroupOut(BaseModel):
    group_id: int
    members: list[LinkedUser]
    matched: list[str]


class LinksResponse(BaseModel):
    flags: list[LinkFlagOut]  # open flags, oldest first
    groups: list[ProfileGroupOut]  # profile groups with two or more accounts


class OverageDecision(BaseModel):
    # "reverse" (claw the overpaid gross back) is planned for a later round (spec Q2).
    action: Literal["keep"]
