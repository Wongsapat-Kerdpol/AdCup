"""Read side of linked account detection: withdrawal holds and what admins see.
See docs/linked-account-detection-spec.md (D6, D11, D14, sections 5.5 and 8).

withdrawals_on_hold(db, user)  -> an open flag involves the user's profile group (spec D11):
                                  "suspected" or "overage" naming a member, or a "hub" flag on a payout
                                  account a member uses (possible mule account). Hubs of a Google account
                                  or an email only alert admins (spec D6) and don't hold anything.
capped_campaigns(db, user)     -> campaigns where the user's group has used its cap per profile (My Submissions).
review_info(db, submission)    -> the extra fields of the admin review queue (computed when read, 5.5).

Admins see which TYPES of signal matched, never the values (spec D14).
"""

from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.identity import IdentitySignal, LinkFlag, LinkFlagKind, LinkFlagStatus, ManualLink, SignalType
from app.models.submission import Submission
from app.models.user import User
from app.schemas.linked_accounts import LinkedAccount, OpenLinkFlag
from app.services.linking import STRONG_SIGNALS


def group_member_ids(db: Session, user: User) -> list[int]:
    if user.profile_group_id is None:
        return [user.id]
    return list(db.scalars(select(User.id).where(User.profile_group_id == user.profile_group_id).order_by(User.id)))


def _involves(member_ids: list[int]):
    return or_(LinkFlag.user_a_id.in_(member_ids), LinkFlag.user_b_id.in_(member_ids))


def withdrawals_on_hold(db: Session, user: User) -> bool:
    members = group_member_ids(db, user)
    payout_values = select(IdentitySignal.value_hash).where(
        IdentitySignal.user_id.in_(members), IdentitySignal.type == SignalType.payout_account
    )
    hold = or_(
        and_(LinkFlag.kind.in_([LinkFlagKind.suspected, LinkFlagKind.overage]), _involves(members)),
        and_(
            LinkFlag.kind == LinkFlagKind.hub,
            LinkFlag.signal_type == SignalType.payout_account,
            LinkFlag.value_hash.in_(payout_values),
        ),
    )
    return db.scalar(select(LinkFlag.id).where(LinkFlag.status == LinkFlagStatus.open, hold).limit(1)) is not None


def matched_types(db: Session, user_ids: list[int]) -> list[str]:
    """Strong signal types (and "manual" for an admin-confirmed link) shared by at least two of these accounts."""
    shared = db.scalars(
        select(IdentitySignal.type)
        .where(
            IdentitySignal.user_id.in_(user_ids),
            IdentitySignal.type.in_(STRONG_SIGNALS),
            IdentitySignal.dismissed.is_(False),
        )
        .group_by(IdentitySignal.type, IdentitySignal.value_hash)
        .having(func.count(IdentitySignal.user_id.distinct()) > 1)
    ).all()
    types = [t.value for t in STRONG_SIGNALS if t in set(shared)]
    manual = db.scalar(
        select(ManualLink.id).where(ManualLink.user_a_id.in_(user_ids), ManualLink.user_b_id.in_(user_ids)).limit(1)
    )
    return types + (["manual"] if manual is not None else [])


def group_gross(db: Session, member_ids: list[int], campaign_id: int) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(Submission.gross_amount), 0)).where(
            Submission.creator_id.in_(member_ids), Submission.campaign_id == campaign_id
        )
    )


def capped_campaigns(db: Session, user: User) -> set[int]:
    """Campaigns where the user's profile group has been paid its whole cap per profile. The creator only
    sees "Cap per profile reached", never that other accounts count towards it (spec D16)."""
    members = group_member_ids(db, user)
    paid = func.sum(Submission.gross_amount)
    return set(
        db.scalars(
            select(Submission.campaign_id)
            .join(Campaign, Campaign.id == Submission.campaign_id)
            .where(Submission.creator_id.in_(members), Campaign.cap_per_profile.is_not(None))
            .group_by(Submission.campaign_id, Campaign.cap_per_profile)
            .having(paid >= Campaign.cap_per_profile)
        ).all()
    )


def review_info(db: Session, submission: Submission) -> dict:
    """linked_accounts, group_gross_in_campaign, cap_per_profile and open_flags for one queued submission."""
    creator = db.get(User, submission.creator_id)
    campaign = db.get(Campaign, submission.campaign_id)
    members = group_member_ids(db, creator)

    linked = db.execute(
        select(User.id, User.display_name)
        .where(
            User.id.in_(members),
            User.id != creator.id,
            User.id.in_(select(Submission.creator_id).where(Submission.campaign_id == campaign.id)),
        )
        .order_by(User.id)
    ).all()
    flags = db.scalars(
        select(LinkFlag)
        .where(
            LinkFlag.status == LinkFlagStatus.open,
            LinkFlag.kind.in_([LinkFlagKind.suspected, LinkFlagKind.overage]),
            LinkFlag.campaign_id == campaign.id,
            _involves(members),
        )
        .order_by(LinkFlag.id)
    ).all()

    open_flags = []
    for flag in flags:
        other_id = None
        if flag.kind == LinkFlagKind.suspected:
            other_id = flag.user_b_id if flag.user_a_id in members else flag.user_a_id
        other = db.get(User, other_id) if other_id else None
        open_flags.append(
            OpenLinkFlag(
                id=flag.id,
                kind=flag.kind,
                reasons=flag.reasons,
                score=flag.score,
                amount=flag.amount,
                other_user_id=other.id if other else None,
                other_display_name=other.display_name if other else None,
            )
        )

    return dict(
        linked_accounts=[
            LinkedAccount(user_id=uid, display_name=name, matched=matched_types(db, [creator.id, uid]))
            for uid, name in linked
        ],
        group_gross_in_campaign=group_gross(db, members, campaign.id),
        cap_per_profile=campaign.cap_per_profile,
        open_flags=open_flags,
    )
