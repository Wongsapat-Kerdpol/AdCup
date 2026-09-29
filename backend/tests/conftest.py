"""[PERSON 2] Shared pytest fixtures for the submission/review/payout test suite.

Uses a dedicated `adcup_test` database on the same Postgres server the app already talks to
(Campaign.platforms is a Postgres ARRAY column, so SQLite can't stand in) — created
automatically on first run. Each test runs inside a transaction that's rolled back afterwards,
so tests never see each other's data and never touch the dev/seed database.

Run with the stack up: `docker compose exec backend pytest` (or `pytest` in a local venv with
DATABASE_URL pointed at localhost).
"""

import os
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  registers every model on Base.metadata
from app.core.config import settings
from app.core.database import Base
from app.core.security import hash_password
from app.models.campaign import Campaign, CampaignCategory, CampaignStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.services import youtube as yt


def _test_database_url() -> str:
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    base = settings.database_url.rsplit("/", 1)[0]
    return f"{base}/adcup_test"


@pytest.fixture(scope="session")
def engine():
    test_url = _test_database_url()
    db_name = test_url.rsplit("/", 1)[-1]
    admin_url = f"{test_url.rsplit('/', 1)[0]}/postgres"

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    eng = create_engine(test_url)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine) -> Generator[Session, None, None]:
    """One session per test, bound to a connection whose outer transaction is always rolled
    back — app code's own db.commit() calls only release a savepoint, so nothing persists."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def make_user(db):
    counter = iter(range(1, 10_000))

    def _make(role: UserRole = UserRole.creator, **kwargs) -> User:
        n = next(counter)
        user = User(
            email=kwargs.pop("email", f"{role.value}{n}@test.dev"),
            password_hash=hash_password("password123"),
            display_name=kwargs.pop("display_name", f"Test {role.value.title()} {n}"),
            role=role,
            **kwargs,
        )
        db.add(user)
        db.flush()
        return user

    return _make


@pytest.fixture()
def make_campaign(db, make_user):
    def _make(brand: User | None = None, *, fund: bool = True, **kwargs) -> Campaign:
        brand = brand or make_user(UserRole.brand)
        campaign = Campaign(
            brand_id=brand.id,
            title=kwargs.pop("title", "Test Campaign"),
            category=kwargs.pop("category", CampaignCategory.ugc),
            platforms=kwargs.pop("platforms", ["youtube"]),
            rate_per_1k_views=kwargs.pop("rate_per_1k_views", Decimal("1.00")),
            total_budget=kwargs.pop("total_budget", Decimal("1000.00")),
            min_views=kwargs.pop("min_views", 1000),
            status=CampaignStatus.draft,
            is_funded=False,
            **kwargs,
        )
        db.add(campaign)
        db.flush()
        if fund:
            campaign.is_funded = True
            campaign.status = CampaignStatus.active
            tx = Transaction(
                user_id=brand.id,
                campaign_id=campaign.id,
                type=TransactionType.campaign_fund,
                status=TransactionStatus.completed,
                gross_amount=campaign.total_budget,
                commission_amount=Decimal("0"),
                net_amount=campaign.total_budget,
            )
            db.add(tx)
            db.flush()
            db.refresh(tx)  # populate the server-side created_at we use as "campaign start"
        return campaign

    return _make


@pytest.fixture()
def make_submission(db):
    counter = iter(range(1, 10_000))

    def _make(campaign: Campaign, creator: User, **kwargs) -> Submission:
        n = next(counter)
        submission = Submission(
            campaign_id=campaign.id,
            creator_id=creator.id,
            video_url=kwargs.pop("video_url", f"https://youtu.be/vid{n:08d}"),
            platform=kwargs.pop("platform", "youtube"),
            external_video_id=kwargs.pop("external_video_id", f"vid{n:08d}"),
            status=kwargs.pop("status", SubmissionStatus.pending),
            view_count=kwargs.pop("view_count", 0),
            **kwargs,
        )
        db.add(submission)
        db.flush()
        return submission

    return _make


@pytest.fixture()
def video_info_factory():
    def _make(**overrides) -> yt.VideoInfo:
        defaults = dict(
            video_id="vid00000001",
            channel_id="channel-1",
            title="Test Video",
            description="",
            tags=[],
            # Default: "now" — tests create the campaign (and its funded_at) first, so a video
            # published at the moment of the call is naturally after campaign start unless a
            # test overrides published_at to check that condition explicitly.
            published_at=datetime.now(timezone.utc),
            view_count=5000,
            is_public=True,
        )
        defaults.update(overrides)
        return yt.VideoInfo(**defaults)

    return _make
