"""Profile groups — which creator accounts are one person (docs/linked-account-detection-spec.md, section 6).

Accounts that share a STRONG signal (payout account, Google account, normalized email) are the same
person, and so is every account linked to them in turn: A~B and B~C puts A, B and C in one group.
That is exactly what a Disjoint Set Union (Union-Find) computes. Each creator's group is written to
users.profile_group_id (the smallest user id in the group), which the payout engine uses for the
cap per profile. Weak signals (device, IP) never merge groups; they only raise flags (Phase 4).

rebuild_profile_groups() recomputes every group from the stored signals instead of patching them,
because Union-Find can't split a group again — rebuilding is what lets an admin undo a link
(dismiss a signal) later. A few thousand accounts take milliseconds: O(S·α(n)) for S signals.

Hub rule (MAX_SHARE): one value shared by more than MAX_SHARE accounts gets a "hub" flag for an admin.
A Google account is then NOT used to merge (an agency may manage many creators' channels); a payout
account and an email still merge (whoever receives the money is one profile).

After a rebuild, groups that gained members are checked for an "overage": linked accounts that were
already paid more than one cap per profile in a campaign before the link was known (spec 6.4).

Callers manage their own db.commit(); this module only flushes.
"""

from collections import defaultdict

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import MAX_SHARE
from app.models.campaign import Campaign
from app.models.identity import IdentitySignal, LinkFlag, LinkFlagKind, LinkFlagStatus, ManualLink, SignalType
from app.models.submission import Submission
from app.models.user import User, UserRole

STRONG_SIGNALS = (SignalType.payout_account, SignalType.google_sub, SignalType.email_norm)
_REBUILD_LOCK = 0x4C494E4B  # pg advisory lock id ("LINK"): one rebuild at a time


class DSU:
    """Disjoint Set Union with path compression and union by rank: ~O(α(n)) per operation."""

    def __init__(self, ids):
        self.parent = {i: i for i in ids}
        self.rank = {i: 0 for i in ids}

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # path compression
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:  # union by rank: the shorter tree goes under the taller one
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def _flag_hub(db: Session, signal_type: SignalType, value_hash: str) -> None:
    """One hub flag per shared value. Once an admin has decided it, rebuilding doesn't raise it again."""
    exists = db.scalar(
        select(LinkFlag.id).where(
            LinkFlag.kind == LinkFlagKind.hub, LinkFlag.signal_type == signal_type, LinkFlag.value_hash == value_hash
        )
    )
    if exists is None:
        db.add(
            LinkFlag(kind=LinkFlagKind.hub, signal_type=signal_type, value_hash=value_hash, reasons=[signal_type.value])
        )


def rebuild_profile_groups(db: Session) -> set[int]:
    """Recompute every creator's profile_group_id. Returns the ids of the users whose group changed."""
    db.execute(select(func.pg_advisory_xact_lock(_REBUILD_LOCK)))  # released at commit / rollback

    current: dict[int, int | None] = {
        user_id: group_id
        for user_id, group_id in db.execute(
            select(User.id, User.profile_group_id).where(User.role == UserRole.creator)
        )
    }
    dsu = DSU(current)

    # Who shares each strong value. Only creators are nodes (spec D18).
    sharing: dict[tuple[SignalType, str], list[int]] = defaultdict(list)
    for signal_type, value_hash, user_id in db.execute(
        select(IdentitySignal.type, IdentitySignal.value_hash, IdentitySignal.user_id)
        .join(User, User.id == IdentitySignal.user_id)
        .where(
            User.role == UserRole.creator,
            IdentitySignal.type.in_(STRONG_SIGNALS),
            IdentitySignal.dismissed.is_(False),
        )
        .order_by(IdentitySignal.user_id)
    ):
        sharing[(signal_type, value_hash)].append(user_id)

    for (signal_type, value_hash), users in sharing.items():
        if len(users) < 2:
            continue
        if len(users) > MAX_SHARE:
            _flag_hub(db, signal_type, value_hash)
            if signal_type == SignalType.google_sub:
                continue
        for user_id in users[1:]:  # star: k accounts need k-1 unions
            dsu.union(users[0], user_id)

    for a, b in db.execute(select(ManualLink.user_a_id, ManualLink.user_b_id)):
        if a in current and b in current:
            dsu.union(a, b)

    smallest: dict[int, int] = {}
    for user_id in current:
        root = dsu.find(user_id)
        smallest[root] = min(smallest.get(root, user_id), user_id)

    moves: dict[int, list[int]] = defaultdict(list)  # new group id -> users moving into it
    for user_id, old_group in current.items():
        new_group = smallest[dsu.find(user_id)]
        if new_group != old_group:
            moves[new_group].append(user_id)
    for group_id, user_ids in moves.items():
        db.execute(update(User).where(User.id.in_(user_ids)).values(profile_group_id=group_id))
    db.flush()

    _flag_overages(db, set(moves))
    db.flush()
    return {user_id for user_ids in moves.values() for user_id in user_ids}


def _flag_overages(db: Session, group_ids: set[int]) -> None:
    """Spec 6.4: groups that just gained members may already have been paid more than cap_per_profile
    in a campaign (each account was paid up to its own cap before they were linked).

    Nothing is clawed back automatically (spec D10): the payout engine already pays the group 0 from
    now on, and an open "overage" flag holds the group's withdrawals until an admin decides.
    The flag points at the group through user_a_id (its smallest member when flagged).
    """
    if not group_ids:
        return
    paid = func.sum(Submission.gross_amount)
    over_cap = db.execute(
        select(User.profile_group_id, Submission.campaign_id, paid - Campaign.cap_per_profile)
        .join(Submission, Submission.creator_id == User.id)
        .join(Campaign, Campaign.id == Submission.campaign_id)
        .where(User.profile_group_id.in_(group_ids), Campaign.cap_per_profile.is_not(None))
        .group_by(User.profile_group_id, Submission.campaign_id, Campaign.cap_per_profile)
        .having(paid > Campaign.cap_per_profile)
    ).all()

    for group_id, campaign_id, excess in over_cap:
        members = select(User.id).where(User.profile_group_id == group_id)
        flag = db.scalar(
            select(LinkFlag)
            .where(
                LinkFlag.kind == LinkFlagKind.overage,
                LinkFlag.campaign_id == campaign_id,
                LinkFlag.user_a_id.in_(members),
            )
            .order_by(LinkFlag.id.desc())
        )
        if flag is not None and flag.status == LinkFlagStatus.open:
            flag.amount = excess  # the group grew again before an admin looked at it
        elif flag is None or excess > flag.amount:  # decided before: only a bigger overage is news
            db.add(
                LinkFlag(
                    kind=LinkFlagKind.overage, user_a_id=group_id, campaign_id=campaign_id, amount=excess, reasons=[]
                )
            )
