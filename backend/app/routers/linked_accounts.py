"""Linked account detection — admin decisions (docs/linked-account-detection-spec.md, section 8).

Approving a video's content stays in the review queue (routers/review.py). Whether two accounts are
the same person is decided here (spec D12). Strong links need no decision (D13); every action only
closes a flag, so withdrawals held by it are released (D11).

  GET  /api/admin/links                              — open flags + profile groups with 2+ accounts
  POST /api/admin/link-flags/{id}/confirm            — suspected: same person -> manual link, caps merged
  POST /api/admin/link-flags/{id}/dismiss            — suspected: different people
                                                       (not raised again on the same evidence)
  POST /api/admin/link-flags/{id}/ignore-signal      — hub of a Google account / email (agency, manager):
                                                       stop using that value to link -> accounts split again
  POST /api/admin/link-flags/{id}/release            — hub of a payout account, checked: release withdrawals
                                                       (still one profile — one payee is one person, D17)
  POST /api/admin/link-flags/{id}/resolve-overage    — overage: "keep" the paid amount ("reverse" comes later, Q2)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign
from app.models.identity import IdentitySignal, LinkFlag, LinkFlagKind, LinkFlagStatus, ManualLink, SignalType
from app.models.user import User, UserRole
from app.schemas.linked_accounts import LinkedUser, LinkFlagOut, LinksResponse, OverageDecision, ProfileGroupOut
from app.services.link_review import group_gross, group_member_ids, matched_types
from app.services.linking import rebuild_profile_groups

router = APIRouter(prefix="/api/admin", tags=["linked accounts"])


def _users(db: Session, ids) -> list[LinkedUser]:
    rows = db.execute(select(User.id, User.display_name).where(User.id.in_(ids)).order_by(User.id)).all()
    return [LinkedUser(id=i, display_name=name) for i, name in rows]


def _flag_out(db: Session, flag: LinkFlag) -> LinkFlagOut:
    campaign = db.get(Campaign, flag.campaign_id) if flag.campaign_id else None
    out = LinkFlagOut(
        id=flag.id,
        kind=flag.kind,
        status=flag.status,
        created_at=flag.created_at,
        users=[],
        reasons=flag.reasons,
        score=flag.score,
        signal_type=flag.signal_type,
        campaign_id=flag.campaign_id,
        campaign_title=campaign.title if campaign else None,
        amount=flag.amount,
    )
    if flag.kind == LinkFlagKind.suspected:
        out.users = _users(db, [flag.user_a_id, flag.user_b_id])
    elif flag.kind == LinkFlagKind.hub:
        sharing = select(IdentitySignal.user_id).where(
            IdentitySignal.type == flag.signal_type, IdentitySignal.value_hash == flag.value_hash
        )
        out.users = _users(db, sharing)
    else:  # overage: the group the flagged account is in now
        members = group_member_ids(db, db.get(User, flag.user_a_id))
        out.users = _users(db, members)
        out.group_gross = group_gross(db, members, flag.campaign_id)
        out.cap_per_profile = campaign.cap_per_profile if campaign else None
    return out


@router.get("/links", response_model=LinksResponse)
def list_links(_: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    flags = db.scalars(select(LinkFlag).where(LinkFlag.status == LinkFlagStatus.open).order_by(LinkFlag.id)).all()
    group_ids = db.scalars(
        select(User.profile_group_id)
        .where(User.profile_group_id.is_not(None))
        .group_by(User.profile_group_id)
        .having(func.count() > 1)
        .order_by(User.profile_group_id)
    ).all()
    groups = []
    for group_id in group_ids:
        member_ids = list(db.scalars(select(User.id).where(User.profile_group_id == group_id)))
        groups.append(
            ProfileGroupOut(group_id=group_id, members=_users(db, member_ids), matched=matched_types(db, member_ids))
        )
    return LinksResponse(flags=[_flag_out(db, f) for f in flags], groups=groups)


def _open_flag(db: Session, flag_id: int, kind: LinkFlagKind) -> LinkFlag:
    flag = db.get(LinkFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    if flag.kind != kind:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This action is for {kind.value} flags")
    if flag.status != LinkFlagStatus.open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This flag has already been decided")
    return flag


def _decide(db: Session, flag: LinkFlag, admin: User, new_status: LinkFlagStatus) -> LinkFlagOut:
    flag.status = new_status
    flag.decided_by_id = admin.id
    flag.decided_at = datetime.now(timezone.utc)
    db.flush()
    out = _flag_out(db, flag)
    db.commit()
    return out


@router.post("/link-flags/{flag_id}/confirm", response_model=LinkFlagOut)
def confirm(flag_id: int, admin: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    flag = _open_flag(db, flag_id, LinkFlagKind.suspected)
    db.add(
        ManualLink(
            user_a_id=flag.user_a_id, user_b_id=flag.user_b_id, admin_id=admin.id, note=f"Confirmed flag #{flag.id}"
        )
    )
    db.flush()
    rebuild_profile_groups(db)  # caps are merged now; an overage flag follows if they were already overpaid
    return _decide(db, flag, admin, LinkFlagStatus.confirmed)


@router.post("/link-flags/{flag_id}/dismiss", response_model=LinkFlagOut)
def dismiss(flag_id: int, admin: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    flag = _open_flag(db, flag_id, LinkFlagKind.suspected)
    return _decide(db, flag, admin, LinkFlagStatus.dismissed)  # nothing was merged, so nothing to rebuild


@router.post("/link-flags/{flag_id}/ignore-signal", response_model=LinkFlagOut)
def ignore_signal(flag_id: int, admin: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    flag = _open_flag(db, flag_id, LinkFlagKind.hub)
    if flag.signal_type == SignalType.payout_account:  # spec D17: one payee is always one person
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A shared payout account can't be ignored — release it instead",
        )
    db.execute(
        update(IdentitySignal)
        .where(IdentitySignal.type == flag.signal_type, IdentitySignal.value_hash == flag.value_hash)
        .values(dismissed=True)
    )
    rebuild_profile_groups(db)
    return _decide(db, flag, admin, LinkFlagStatus.resolved)


@router.post("/link-flags/{flag_id}/release", response_model=LinkFlagOut)
def release(flag_id: int, admin: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    flag = _open_flag(db, flag_id, LinkFlagKind.hub)
    if flag.signal_type != SignalType.payout_account:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a shared payout account is released — ignore this signal",
        )
    return _decide(db, flag, admin, LinkFlagStatus.resolved)


@router.post("/link-flags/{flag_id}/resolve-overage", response_model=LinkFlagOut)
def resolve_overage(
    flag_id: int,
    body: OverageDecision,
    admin: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    flag = _open_flag(db, flag_id, LinkFlagKind.overage)
    # body.action == "keep": the creators keep what they were paid; future payouts already respect the group cap.
    return _decide(db, flag, admin, LinkFlagStatus.resolved)
