"""Campaign outlook — "is this campaign still worth making a video for?"

The pool number on the Discover page is misleading: videos that are already approved keep
gaining views, so part of the pool is already spoken for. This module projects those claims and
answers two questions with the algorithms in services/allocation.py:

  1. When will the pool run dry?   Money claimed by day t only ever grows with t, so we
                                   binary-search the first day it reaches the pool
                                   (O(n log days) instead of simulating every day).
  2. What would MY video earn?     Replay the payout rounds the platform will run (one per day):
                                   everybody is paid in full until the pool runs out, and in the
                                   round where it runs out everybody gets the same percentage of
                                   what they earned. A new video only joins after it has been
                                   reviewed, so the backlog that approved videos have already
                                   earned is paid out before it.

Projection model (deliberately simple — see the README section on the outlook for caveats):
  - a video keeps gaining views at its average rate so far: view_count / age_in_days
  - claims are capped by cap_per_post; cap_per_profile is ignored (needs per-creator state)
  - payout rounds run once a day; a video posted today is approved REVIEW_DELAY_DAYS later and
    is then paid for all the views it gained since it was posted
  - the new video gains `views_per_day`, by default the median of the existing videos
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import COMMISSION_RATE, DEFAULT_MIN_VIEWS
from app.models.campaign import Campaign, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.services.allocation import first_step_reaching, proportional_share
from app.services.payout import from_satang, to_satang

DEFAULT_HORIZON_DAYS = 30  # used when the campaign has no deadline
MAX_HORIZON_DAYS = 90  # never project further than this — the farther, the less the average rate means
FALLBACK_DAYS_TO_MIN_VIEWS = 7  # no videos yet: assume a typical video reaches min_views in a week
REVIEW_DELAY_DAYS = 2  # a video posted today is system-checked, reviewed and approved this many days later

OPEN, COMPETITIVE, CROWDED, CLOSED = "open", "competitive", "crowded", "closed"


@dataclass
class Newcomer:
    views_per_day: float
    assumption: str  # "input" | "median" | "default"
    expected_gross: Decimal
    expected_net: Decimal
    fill_ratio: float | None  # share of what the video would earn that the pool can actually pay


@dataclass
class Outlook:
    verdict: str
    pool_remaining: Decimal
    horizon_days: int
    projected_claims: Decimal  # what approved videos are expected to claim within the horizon
    pressure: float | None  # projected_claims / pool_remaining (> 1: pool will not cover everyone)
    exhausted_in_days: int | None
    exhausted_on: date | None
    approved_videos: int
    in_review_videos: int
    newcomer: Newcomer


@dataclass
class _Video:
    views_per_day: float
    unpaid_views: int
    cap_left_satang: int | None  # None: no per-post cap


def _horizon_days(campaign: Campaign, now: datetime) -> int:
    if campaign.deadline is None:
        return DEFAULT_HORIZON_DAYS
    days = math.ceil((campaign.deadline - now).total_seconds() / 86400)
    return max(1, min(days, MAX_HORIZON_DAYS))


def _claim_satang(campaign: Campaign, unpaid_views: float, cap_left: int | None) -> int:
    gross = Decimal(str(unpaid_views)) / Decimal(1000) * campaign.rate_per_1k_views
    satang = to_satang(gross)
    return satang if cap_left is None else min(satang, max(cap_left, 0))


def _load_videos(db: Session, campaign: Campaign, now: datetime) -> list[_Video]:
    rows = db.scalars(
        select(Submission).where(Submission.campaign_id == campaign.id, Submission.status == SubmissionStatus.approved)
    ).all()
    videos = []
    for s in rows:
        started = s.video_published_at or s.approved_at or s.created_at
        age_days = max((now - started).total_seconds() / 86400, 1.0)
        cap_left = None
        if campaign.cap_per_post is not None:
            cap_left = to_satang(campaign.cap_per_post - s.gross_amount)
        videos.append(_Video(s.view_count / age_days, max(s.view_count - s.paid_views, 0), cap_left))
    return videos


def campaign_outlook(
    db: Session, campaign: Campaign, views_per_day: float | None = None, now: datetime | None = None
) -> Outlook:
    now = now or datetime.now(timezone.utc)
    horizon = _horizon_days(campaign, now)
    pool = to_satang(campaign.remaining_budget)
    videos = _load_videos(db, campaign, now)

    def claims_at(day: int) -> list[int]:
        """What each approved video will have claimed in total by the end of `day` (day 0 = backlog)."""
        return [_claim_satang(campaign, v.unpaid_views + v.views_per_day * day, v.cap_left_satang) for v in videos]

    def total_at(day: int) -> int:
        return sum(claims_at(day))

    # 1) when does the pool run dry?  (binary search on the answer)
    exhausted_in = first_step_reaching(pool, total_at, 0, horizon) if pool > 0 and videos else None
    projected = total_at(horizon)

    # 2) what would a new video earn?
    if views_per_day is not None:
        assumption, vpd = "input", views_per_day
    elif videos:
        assumption, vpd = "median", float(median(v.views_per_day for v in videos))
    else:
        min_views = campaign.min_views or DEFAULT_MIN_VIEWS
        assumption, vpd = "default", min_views / FALLBACK_DAYS_TO_MIN_VIEWS
    cap_post = to_satang(campaign.cap_per_post) if campaign.cap_per_post is not None else None

    def mine_at(day: int) -> int:
        """Cumulative claim of the new video: nothing until it is approved, then everything since posting."""
        return _claim_satang(campaign, vpd * day, cap_post) if day >= REVIEW_DELAY_DAYS else 0

    def everyone_at(day: int) -> int:
        return 0 if day == 0 else total_at(day) + mine_at(day)  # nothing has been paid before round 1

    full_claim = mine_at(horizon)  # what it would earn if the pool never ran out
    if full_claim == 0:
        earned = 0
    else:
        # Rounds run daily. Everybody is paid in full until the pool is short, so find the first round
        # whose cumulative claims reach the pool (binary search again) ...
        last_round = first_step_reaching(pool, everyone_at, 1, horizon) if pool > 0 else 1
        if last_round is None:
            earned = full_claim
        else:
            # ... then share what is left in that round proportionally; later rounds pay nothing.
            before = [0] * len(videos) if last_round == 1 else claims_at(last_round - 1)
            demands = [after - prior for after, prior in zip(claims_at(last_round), before)]
            demands.append(mine_at(last_round) - mine_at(last_round - 1))
            round_pool = pool - everyone_at(last_round - 1)
            earned = mine_at(last_round - 1) + proportional_share(demands, max(round_pool, 0))[-1]
    fill = earned / full_claim if full_claim > 0 else None

    gross = from_satang(earned)
    newcomer = Newcomer(
        views_per_day=round(vpd, 1),
        assumption=assumption,
        expected_gross=gross,
        expected_net=(gross * (1 - COMMISSION_RATE)).quantize(Decimal("0.01")),
        fill_ratio=None if fill is None else round(fill, 3),
    )

    if campaign.status != CampaignStatus.active or pool <= 0 or horizon < REVIEW_DELAY_DAYS:
        verdict = CLOSED  # not paying, or it ends before a video posted today could be approved
    elif fill is None:
        verdict = CROWDED if projected >= pool else OPEN  # no video to judge (0 views/day): judge the pool
    elif fill >= 0.95:
        verdict = OPEN
    elif fill >= 0.6:
        verdict = COMPETITIVE
    else:
        verdict = CROWDED

    in_review = db.scalar(
        select(func.count()).where(
            Submission.campaign_id == campaign.id,
            Submission.status.in_([SubmissionStatus.under_review, SubmissionStatus.pending]),
        )
    )
    return Outlook(
        verdict=verdict,
        pool_remaining=campaign.remaining_budget,
        horizon_days=horizon,
        projected_claims=from_satang(projected),
        pressure=round(projected / pool, 2) if pool > 0 else None,
        exhausted_in_days=exhausted_in,
        exhausted_on=(now + timedelta(days=exhausted_in)).date() if exhausted_in is not None else None,
        approved_videos=len(videos),
        in_review_videos=in_review or 0,
        newcomer=newcomer,
    )
