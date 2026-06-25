"""Application configuration using Pydantic Settings.

Loads configuration from environment variables with sensible defaults
for local development.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/douyin_shop"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Douyin (抖店) API Credentials ---
    DOUYIN_APP_KEY: str = ""
    DOUYIN_APP_SECRET: str = ""
    DOUYIN_ACCESS_TOKEN: str = ""
    DOUYIN_REFRESH_TOKEN: str = ""

    # --- AI Service ---
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://api.openai.com/v1"

    # --- Third-party Data Platforms ---
    CHANMAMA_API_KEY: str = ""
    FEIGUA_API_KEY: str = ""

    # --- 1688 Supply Chain ---
    ALIBABA_1688_APP_KEY: str = ""
    ALIBABA_1688_APP_SECRET: str = ""
    # OAuth access token for the 1688 trade (下单) APIs. Search APIs only need
    # the app key, but order placement / logistics require an authorized token.
    ALIBABA_1688_ACCESS_TOKEN: str = ""

    # --- Fulfillment (selection -> listing -> 1688 order -> logistics) ---
    # Target gross-margin floor used when pricing a listing. 0.10 == 10%.
    FULFILLMENT_TARGET_MARGIN: float = 0.10
    # Hard floor: never price below this achieved margin even after rounding.
    FULFILLMENT_MIN_MARGIN: float = 0.10
    # Minimum fused match score (0-1) to accept a 1688 same-source supplier.
    FULFILLMENT_MIN_MATCH_SCORE: float = 0.55
    # Shared secret used to verify inbound 抖店 order push webhooks.
    DOUYIN_ORDER_WEBHOOK_SECRET: str = ""
    # Poll-fallback window (minutes) for ingesting new 抖店 orders.
    FULFILLMENT_ORDER_POLL_LOOKBACK_MINUTES: int = 30

    # --- Object Storage (OSS) ---
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_BUCKET: str = "douyin-shop-assets"
    OSS_ENDPOINT: str = "https://oss-cn-hangzhou.aliyuncs.com"

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"


settings = Settings()
