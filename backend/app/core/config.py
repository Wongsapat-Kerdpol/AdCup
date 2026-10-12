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

# --- Linked account detection (docs/linked-account-detection-spec.md) ---
MAX_SHARE = 3  # a strong signal shared by more accounts than this is a "hub" (agency, mule account): flagged
