"""News aggregation API."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_redis
from app.services.news_aggregator import NewsAggregationService

router = APIRouter()


class NewsDigestWindowResponse(BaseModel):
    start: str
    end: str
    timezone: str
    label: str


class NewsTopicResponse(BaseModel):
    topic: str
    count: int
    sources: List[str] = Field(default_factory=list)


class NewsSourceResponse(BaseModel):
    id: str
    name: str
    feed_url: str
    homepage_url: Optional[str] = None
    article_count: int = 0
    status: str = "ok"
    last_error: Optional[str] = None
    fetched_at: Optional[str] = None


class NewsDigestItemResponse(BaseModel):
    id: str
    title: str
    source_id: str
    source_name: str
    url: str
    published_at: str
    summary: str
    highlights: List[str] = Field(default_factory=list)
    excerpt: str = ""


class NewsDigestResponse(BaseModel):
    window: NewsDigestWindowResponse
    refreshed_at: str
    total_sources: int
    total_articles: int
    topics: List[NewsTopicResponse] = Field(default_factory=list)
    sources: List[NewsSourceResponse] = Field(default_factory=list)
    items: List[NewsDigestItemResponse] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


@router.get("/digest", response_model=NewsDigestResponse)
async def get_news_digest(
    refresh: bool = Query(False, description="Force refresh instead of using cached digest"),
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    """Get the latest completed daily news digest."""
    service = NewsAggregationService()
    return await service.get_digest(redis=redis, force_refresh=refresh)


@router.post("/digest/refresh", response_model=NewsDigestResponse)
async def refresh_news_digest(redis: Any = Depends(get_redis)) -> dict[str, Any]:
    """Force rebuild the latest daily digest."""
    service = NewsAggregationService()
    return await service.get_digest(redis=redis, force_refresh=True)


@router.get("/sources", response_model=List[NewsSourceResponse])
async def get_news_sources() -> list[dict[str, Any]]:
    """List configured news sources."""
    service = NewsAggregationService()
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "feed_url": item["feed_url"],
            "homepage_url": item.get("homepage_url") or None,
            "article_count": 0,
            "status": "configured",
            "last_error": None,
            "fetched_at": None,
        }
        for item in service.get_sources()
    ]
