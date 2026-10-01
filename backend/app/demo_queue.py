"""Demo data so the campaign outlook and payout rounds have something to show.

The normal seed creates campaigns but no videos. This adds two clearly named demo campaigns, each
with fake creators and approved videos (plus a few waiting for review):

  "Demo - Crowded Campaign"   small pool, many strong videos  -> outlook "crowded", pool already over-claimed
  "Demo - Room To Join"       big pool, a few videos          -> outlook "open"

Only ever run this against a throwaway database — it adds users and campaigns. Safe to re-run (it
skips if the demo creators exist):
    docker compose exec backend python -m app.demo_queue
Then log in as admin@adcup.dev and press "Run payout round" on /admin to see the proportional split.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Campaign, CampaignCategory, CampaignStatus, Submission, SubmissionStatus, User, UserRole

# title, rate THB / 1K views, budget THB, days until deadline, approved videos, videos in review
PLAN = [
    ("Demo - Crowded Campaign", 25, 3000, 30, 10, 2),
    ("Demo - Room To Join", 30, 40000, 25, 4, 1),
]


def main() -> None:
    rng = random.Random(7)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "demo_creator1@adcup.dev")):
            print("Demo data already exists — nothing to do.")
            return
        brand = db.scalar(select(User).where(User.role == UserRole.brand).order_by(User.id))
        if brand is None:
            print("No brand user — start the backend once so the seed runs, then retry.")
            return

        pw = hash_password("password123")
        n_users = 0

        def new_creator() -> User:
            nonlocal n_users
            n_users += 1
            user = User(
                email=f"demo_creator{n_users}@adcup.dev",
                display_name=f"Demo Creator {n_users}",
                role=UserRole.creator,
                password_hash=pw,
            )
            db.add(user)
            db.flush()
            return user

        for title, rate, budget, days_left, approved, in_review in PLAN:
            budget_d = Decimal(budget)
            campaign = Campaign(
                brand_id=brand.id,
                title=title,
                description=f"Demo campaign “{title}” for trying out the outlook and payout rounds.",
                requirements="• Show the product clearly\n• Original content only",
                category=CampaignCategory.ugc,
                platforms=["youtube"],
                rate_per_1k_views=Decimal(rate),
                total_budget=budget_d,
                cap_per_post=(budget_d * Decimal("0.2")).quantize(Decimal("1")),
                cap_per_profile=(budget_d * Decimal("0.4")).quantize(Decimal("1")),
                status=CampaignStatus.active,
                is_funded=True,
                deadline=now + timedelta(days=days_left),
            )
            db.add(campaign)
            db.flush()

            for i in range(approved + in_review):
                creator = new_creator()
                is_approved = i < approved
                published = now - timedelta(days=rng.randint(5, 25))
                views = int(rng.uniform(8_000, 60_000) if is_approved else rng.uniform(1_500, 6_000))
                db.add(
                    Submission(
                        campaign_id=campaign.id,
                        creator_id=creator.id,
                        video_url=f"https://youtu.be/demo{campaign.id:02d}{i:04d}",
                        platform="youtube",
                        external_video_id=f"demo{campaign.id:02d}{i:04d}",
                        video_title=f"{title} — take {i + 1}",
                        video_channel_id=f"demo-channel-{n_users}",
                        video_published_at=published,
                        view_count=views,
                        views_refreshed_at=now,
                        status=SubmissionStatus.approved if is_approved else SubmissionStatus.under_review,
                        system_checked_at=published + timedelta(hours=1),
                        reviewed_at=published + timedelta(days=1) if is_approved else None,
                        approved_at=published + timedelta(days=1) if is_approved else None,
                    )
                )
            print(f"{title}: {approved} approved + {in_review} in review")
        db.commit()


if __name__ == "__main__":
    main()
