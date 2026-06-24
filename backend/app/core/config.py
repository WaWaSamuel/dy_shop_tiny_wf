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

    # --- Object Storage (OSS) ---
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_BUCKET: str = "douyin-shop-assets"
    OSS_ENDPOINT: str = "https://oss-cn-hangzhou.aliyuncs.com"

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"


settings = Settings()
