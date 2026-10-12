"""Central configuration shared by every module. Values come from environment / .env."""

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://adcup:adcup_dev_password@localhost:5432/adcup"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    cors_origins: str = "http://localhost:3000"
    dev_login_enabled: bool = True
    seed_on_startup: bool = True

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/youtube/callback"
    youtube_api_key: str = ""  # public video stats (videos.list); OAuth is only for channel ownership

    # Duplicate-clip checker (dHash + BK-Tree). Turn off to hide the warnings without touching code.
    enable_anti_fraud: bool = True

    # Key for HMAC-hashing identity signals (linked account detection). Raw values are never stored.
    identity_hash_secret: str = "change-me-identity"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# --- Business rules from the proposal (section 6). Import these, don't hard-code. ---
COMMISSION_RATE = Decimal("0.10")  # flat 10% platform commission on every payout
MIN_WITHDRAWAL_THB = Decimal("1500.00")  # creator can withdraw once balance >= this
DEFAULT_MIN_VIEWS = 1000  # round-1 system check: minimum views before admin review (per-campaign override)
SUPPORTED_SUBMISSION_PLATFORMS = ("youtube",)  # add "tiktok", "instagram" once their APIs are integrated
CURRENCY = "THB"

# Duplicate-clip checker (services/duplicate_check.py). Distances are Hamming distances out of 64 bits.
DUPLICATE_MATCH_RADIUS = 8  # a picture "matches" an old one when they differ by at most this many bits
DUPLICATE_NEAR_EXACT = 3  # "almost identical" picture -> yellow "Should check" warning
DUPLICATE_COPY_RATIO = 0.6  # share of pictures matching one old clip -> red "Probably a copy" warning

# --- Linked account detection (docs/linked-account-detection-spec.md) ---
MAX_SHARE = 3  # a strong signal shared by more accounts than this is a "hub" (agency, mule account): flagged
LINK_FLAG_SCORE = 50  # weak-signal risk score at which a pair of accounts is flagged "suspected"
IP_HUB_SIZE = 5  # an IP used by more accounts than this (dorm, campus, mobile carrier NAT) scores nothing
