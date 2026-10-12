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

    # TikTok Login Kit (Person 3). Stats need the creator's own token; redirect URI must be https.
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = ""

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
SUPPORTED_SUBMISSION_PLATFORMS = ("youtube", "tiktok")  # add "instagram" once its adapter exists
CURRENCY = "THB"
