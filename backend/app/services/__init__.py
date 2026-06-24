"""Shared services package for Douyin Shop Automation.

Provides unified clients for external APIs and infrastructure:
- DouyinAPIClient: 抖店 Open API with signing, rate limiting, circuit breaker
- AIService: LLM and image generation with cost tracking
- StorageService: OSS/cloud storage operations
"""

from app.services.ai_service import AIService
from app.services.douyin_api import DouyinAPIClient
from app.services.storage_service import StorageService

__all__ = [
    "DouyinAPIClient",
    "AIService",
    "StorageService",
]
