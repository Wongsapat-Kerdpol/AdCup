"""Demo data so everyone can develop against a populated DB.

Seeded logins (password for all: password123):
  brand@adcup.dev   (Brand)      brand2@adcup.dev (Brand)
  creator@adcup.dev (Creator)    admin@adcup.dev  (Admin)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Campaign, CampaignCategory, CampaignStatus, PayoutMethod, SignalType, User, UserRole
from app.services.identity import normalize_email, normalize_promptpay, record_signal
from app.services.linking import rebuild_profile_groups

DEMO_PASSWORD = "password123"
DEMO_PROMPTPAY = "0800000003"  # fake PromptPay phone for the seeded creator

USERS = [
    ("brand@adcup.dev", "Siam Coffee Co.", UserRole.brand),
    ("brand2@adcup.dev", "Neon Records", UserRole.brand),
    ("creator@adcup.dev", "Mint Creates", UserRole.creator),
    ("admin@adcup.dev", "AdCup Admin", UserRole.admin),
]

# title, category, platforms, rate THB / 1K views, budget THB, paid-out fraction, days left, brand index
CAMPAIGNS = [
    ("Siam Coffee — Morning Ritual [UGC]", "ugc", ["tiktok", "instagram"], 25, 50000, 0.42, 21, 0),
    ("Neon Records — Midnight Drive [EDITS]", "music", ["tiktok", "youtube"], 70, 84000, 0.88, 6, 1),
    ("Thai Street Food Tour [CLIPPING]", "clipping", ["youtube", "tiktok"], 35, 60000, 0.28, 30, 0),
    ("Siam Coffee Logo Placement", "logo", ["youtube", "tiktok", "instagram"], 4.5, 105000, 0.17, 45, 0),
    ("Lo-fi Bangkok Nights [MUSIC]", "music", ["tiktok"], 35, 28000, 0.55, 12, 1),
    ("Esports Highlights — CS2 [LOGO]", "logo", ["youtube", "x"], 3.5, 245000, 0.18, 60, 1),
    ("Skincare Honest Review [UGC]", "ugc", ["tiktok", "instagram"], 30, 40000, 0.04, 25, 0),
    ("Podcast Best Moments [CLIPPING]", "clipping", ["youtube", "tiktok", "instagram"], 28, 70000, 0.89, 4, 1),
    ("Neon Records — Hold Me [EDITS]", "music", ["tiktok", "instagram"], 35, 56000, 0.12, 18, 1),
    ("Muay Thai Gym Promo [UGC]", "ugc", ["youtube", "tiktok"], 20, 35000, 0.0, 40, 0),
    ("Tech Unboxing Shorts [CLIPPING]", "clipping", ["youtube"], 40, 120000, 0.65, 15, 0),
    ("Streetwear Drop Lookbook [LOGO]", "logo", ["instagram", "tiktok"], 5, 90000, 0.31, 28, 1),
    ("Chill Study Beats [MUSIC]", "music", ["youtube", "tiktok"], 24.5, 21000, 0.97, 2, 1),
    ("Healthy Meal Prep Challenge [UGC]", "ugc", ["tiktok", "instagram", "youtube"], 22, 45000, 0.23, 35, 0),
    ("Stand-up Comedy Clips [CLIPPING]", "clipping", ["tiktok", "x"], 30, 52000, 0.47, 22, 1),
    ("Island Travel Vlog [UGC]", "ugc", ["youtube", "instagram"], 26, 64000, 0.08, 50, 0),
]


def seed_if_empty() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            return

        pw = hash_password(DEMO_PASSWORD)
        users = [User(email=e, display_name=n, role=r, password_hash=pw) for e, n, r in USERS]
        db.add_all(users)
        db.flush()
        brands = [u for u in users if u.role == UserRole.brand]

        # Creators get the same identity signals as a web sign-up, plus a (fake) payout account so they can
        # submit right away (linked account detection, spec D8).
        for creator in (u for u in users if u.role == UserRole.creator):
            creator.payout_method = PayoutMethod.promptpay
            creator.payout_account_masked = f"••• {DEMO_PROMPTPAY[-4:]}"
            creator.payout_account_name = creator.display_name
            record_signal(db, creator, SignalType.email_norm, normalize_email(creator.email))
            record_signal(db, creator, SignalType.payout_account, normalize_promptpay(DEMO_PROMPTPAY))
        rebuild_profile_groups(db)

        now = datetime.now(timezone.utc)
        for i, (title, cat, platforms, rate, budget, frac, days, b) in enumerate(CAMPAIGNS):
            budget_d = Decimal(budget)
            db.add(
                Campaign(
                    brand_id=brands[b].id,
                    title=title,
                    description=f"Create an original short-form video for “{title}”. "
                    "Post it on one of the allowed platforms and submit the link.",
                    requirements="• Show the product clearly on screen for at least 3 seconds\n"
                    "• Video must be original content, minimum 10 seconds\n"
                    "• Mention the brand in the title or description\n"
                    "• No reposts or AI-generated voiceovers",
                    category=CampaignCategory(cat),
                    # Submissions are YouTube-only for now, so every demo campaign accepts YouTube.
                    platforms=["youtube"] + [p for p in platforms if p != "youtube"],
                    rate_per_1k_views=Decimal(str(rate)),
                    total_budget=budget_d,
                    paid_out=(budget_d * Decimal(str(frac))).quantize(Decimal("0.01")),
                    cap_per_post=(budget_d * Decimal("0.2")).quantize(Decimal("1")),
                    cap_per_profile=(budget_d * Decimal("0.4")).quantize(Decimal("1")),
                    status=CampaignStatus.active,
                    is_funded=True,
                    deadline=now + timedelta(days=days),
                    created_at=now - timedelta(hours=i * 7),
                )
            )
        db.commit()
