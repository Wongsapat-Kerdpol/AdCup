"""[PERSON 3] Admin analytics.

  GET /api/admin/stats — active users, transaction volume, commission revenue (actual + projected),
                         daily volume, campaign performance, submissions per status.
(The admin submission review queue is Person 2's — see routers/review.py.)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.config import COMMISSION_RATE
from app.core.database import get_db
from app.core.deps import require_role
from app.models.campaign import Campaign, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.schemas.admin import AdminStats, CampaignPerformance, DailyVolume, MoneyStats, UserStats

router = APIRouter(prefix="/api/admin", tags=["admin (Person 3)"])

DAILY_WINDOW_DAYS = 14
TOP_CAMPAIGNS = 8


@router.get("/stats", response_model=AdminStats)
def get_stats(_: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    since_30d = now - timedelta(days=30)
    completed = Transaction.status == TransactionStatus.completed

    # --- Users ---
    by_role = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    active_ids = (
        select(Submission.creator_id.label("uid"))
        .where(Submission.created_at >= since_30d)
        .union(select(Transaction.user_id).where(Transaction.created_at >= since_30d))
        .subquery()
    )
    users = UserStats(
        total=sum(by_role.values()),
        by_role={role: by_role.get(role, 0) for role in UserRole},
        new_last_30d=db.scalar(select(func.count()).where(User.created_at >= since_30d)) or 0,
        active_last_30d=db.scalar(select(func.count()).select_from(active_ids)) or 0,
    )

    # --- Money ---
    def tx_sum(tx_type: TransactionType, column) -> Decimal:
        return db.scalar(select(func.coalesce(func.sum(column), 0)).where(Transaction.type == tx_type, completed))

    locked = db.scalar(
        select(func.coalesce(func.sum(func.greatest(Campaign.total_budget - Campaign.paid_out, 0)), 0)).where(
            Campaign.is_funded, Campaign.status == CampaignStatus.active
        )
    )
    money = MoneyStats(
        total_funded=tx_sum(TransactionType.campaign_fund, Transaction.gross_amount),
        total_paid_out=tx_sum(TransactionType.payout, Transaction.gross_amount),
        commission_revenue=tx_sum(TransactionType.payout, Transaction.commission_amount),
        total_withdrawn=tx_sum(TransactionType.withdrawal, Transaction.net_amount),
        locked_in_pools=locked,
        projected_commission=(Decimal(locked) * COMMISSION_RATE).quantize(Decimal("0.01")),
        transaction_count=db.scalar(select(func.count()).select_from(Transaction).where(completed)) or 0,
    )

    # --- Daily volume (UTC days), zero-filled ---
    first_day = now.date() - timedelta(days=DAILY_WINDOW_DAYS - 1)
    day = cast(func.timezone("UTC", Transaction.created_at), Date)

    def by_type(tx_type: TransactionType, column):
        return func.coalesce(func.sum(case((Transaction.type == tx_type, column), else_=0)), 0)

    rows = db.execute(
        select(
            day,
            by_type(TransactionType.payout, Transaction.gross_amount),
            by_type(TransactionType.payout, Transaction.commission_amount),
            by_type(TransactionType.campaign_fund, Transaction.gross_amount),
        )
        .where(completed, day >= first_day)
        .group_by(day)
    ).all()
    per_day = {d: (paid, com, fund) for d, paid, com, fund in rows}
    daily = []
    for i in range(DAILY_WINDOW_DAYS):
        d = first_day + timedelta(days=i)
        paid, com, fund = per_day.get(d, (0, 0, 0))
        daily.append(DailyVolume(day=d, paid_out=paid, commission=com, funded=fund))

    # --- Status breakdowns ---
    sub_counts = dict(db.execute(select(Submission.status, func.count()).group_by(Submission.status)).all())
    camp_counts = dict(db.execute(select(Campaign.status, func.count()).group_by(Campaign.status)).all())

    # --- Campaign performance (funded campaigns, most paid out first) ---
    approved = Submission.status == SubmissionStatus.approved
    sub_stats = (
        select(
            Submission.campaign_id,
            func.count().label("submissions"),
            func.count().filter(approved).label("approved"),
            func.coalesce(func.sum(Submission.view_count).filter(approved), 0).label("views"),
        )
        .group_by(Submission.campaign_id)
        .subquery()
    )
    top = db.execute(
        select(Campaign, sub_stats.c.submissions, sub_stats.c.approved, sub_stats.c.views)
        .outerjoin(sub_stats, sub_stats.c.campaign_id == Campaign.id)
        .where(Campaign.is_funded)
        .order_by(Campaign.paid_out.desc(), Campaign.id)
        .limit(TOP_CAMPAIGNS)
    ).all()

    return AdminStats(
        users=users,
        money=money,
        daily=daily,
        submissions_by_status={s: sub_counts.get(s, 0) for s in SubmissionStatus},
        campaigns_by_status={s: camp_counts.get(s, 0) for s in CampaignStatus},
        top_campaigns=[
            CampaignPerformance(
                id=c.id,
                title=c.title,
                brand_name=c.brand.display_name,
                status=c.status,
                total_budget=c.total_budget,
                paid_out=c.paid_out,
                paid_out_percent=c.paid_out_percent,
                submissions=n or 0,
                approved=a or 0,
                views=v or 0,
            )
            for c, n, a, v in top
        ],
    )
