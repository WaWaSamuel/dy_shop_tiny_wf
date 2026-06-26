"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "Personal Studio"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Security / JWT
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # PostgreSQL - Write (primary)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/personal_studio"
    # PostgreSQL - Read replica (falls back to primary if not set)
    DATABASE_READ_URL: str = ""

    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"

    # Provider integrations
    PROVIDER_TIMEOUT: int = 30
    PROVIDER_RETRY_COUNT: int = 3

    # AI / Creative
    OPENAI_API_KEY: str = ""
    STABILITY_API_KEY: str = ""

    # Feishu IM Bot
    FEISHU_BOT_ENABLED: bool = False
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_BASE_DOMAIN: str = "https://open.feishu.cn"
    FEISHU_BOT_TARGET_OPEN_ID: str = ""
    FEISHU_BOT_OWNER_ID: str = ""
    FEISHU_BOT_DEFAULT_CHAT_ID: str = ""
    FEISHU_BOT_PUSH_TOKEN: str = ""

    # News aggregation
    NEWS_SOURCE_CONFIG: str = ""
    NEWS_DIGEST_TIMEZONE: str = "Asia/Shanghai"
    NEWS_DIGEST_WINDOW_START_HOUR: int = 21
    NEWS_DIGEST_WINDOW_END_HOUR: int = 9
    NEWS_DIGEST_MAX_ARTICLES: int = 24
    NEWS_DIGEST_MAX_ITEMS_PER_SOURCE: int = 8
    NEWS_DIGEST_REQUEST_TIMEOUT_SECONDS: int = 20
    NEWS_DIGEST_CACHE_TTL_SECONDS: int = 43200
    NEWS_DIGEST_USER_AGENT: str = "DYShop-NewsAggregator/1.0"
    NEWS_DIGEST_ARTICLE_TEXT_LIMIT: int = 1600

    @property
    def database_read_url(self) -> str:
        """Return read replica URL or fall back to primary."""
        return self.DATABASE_READ_URL or self.DATABASE_URL


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
