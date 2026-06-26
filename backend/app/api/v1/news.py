"""News aggregation API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_redis
from app.services.feishu_bot import get_feishu_bot_service
from app.services.news_aggregator import NewsAggregationService
from app.services.weread_digest import WeReadDigestService

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


class NewsDigestPushItemRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    url: Optional[str] = Field(default=None, max_length=2000)
    summary: Optional[str] = Field(default=None, max_length=500)


class NewsDigestPushRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: Optional[str] = Field(default=None, max_length=2000)
    items: List[NewsDigestPushItemRequest] = Field(default_factory=list, max_length=10)
    open_id: Optional[str] = Field(default=None, description="Optional Feishu open_id override")
    chat_id: Optional[str] = Field(default=None, description="Optional Feishu chat_id override")


class NewsDigestPushResponse(BaseModel):
    success: bool = True
    receive_id_type: str
    receive_id: str
    target_hint: str
    message_id: Optional[str] = None


class WeReadSourceResponse(BaseModel):
    id: str
    name: str
    book_id: str
    article_count: int = 0
    status: str = "ok"
    last_error: Optional[str] = None


class WeReadDigestItemResponse(BaseModel):
    id: str
    review_id: str
    title: str
    source_id: str
    source_name: str
    url: str
    published_at: str
    published_label: str
    summary: str
    excerpt: str = ""


class WeReadDigestWindowResponse(BaseModel):
    timezone: str
    start_iso: str
    end_iso: str
    start_label: str
    end_label: str


class WeReadPushResultResponse(BaseModel):
    receive_id_type: str
    receive_id: str
    target_hint: str
    message_id: Optional[str] = None


class WeReadDigestResponse(BaseModel):
    window: WeReadDigestWindowResponse
    refreshed_at: str
    total_sources: int
    total_articles: int
    sources: List[WeReadSourceResponse] = Field(default_factory=list)
    items: List[WeReadDigestItemResponse] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    markdown_file: str
    push_result: Optional[WeReadPushResultResponse] = None


class WeReadDigestBuildRequest(BaseModel):
    start: Optional[datetime] = Field(default=None, description="Optional window start time")
    end: Optional[datetime] = Field(default=None, description="Optional window end time")
    source_names: List[str] = Field(default_factory=list, description="Optional source names to include")
    push_to_feishu: bool = Field(default=False, description="Push the generated digest to Feishu")
    open_id: Optional[str] = Field(default=None, description="Optional Feishu open_id override")
    chat_id: Optional[str] = Field(default=None, description="Optional Feishu chat_id override")


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


@router.post("/digest/push", response_model=NewsDigestPushResponse)
async def push_news_digest(payload: NewsDigestPushRequest) -> dict[str, Any]:
    """Push a curated digest card to Feishu without exposing push token to browser."""
    bot = get_feishu_bot_service()
    if not bot.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feishu bot is not ready.",
        )

    return {
        "success": True,
        **(
            await bot.push_news(
                title=payload.title,
                content=payload.content,
                items=[item.model_dump(exclude_none=True) for item in payload.items],
                open_id=payload.open_id,
                chat_id=payload.chat_id,
            )
        ),
    }


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


@router.post("/weread/digest/build", response_model=WeReadDigestResponse)
async def build_weread_digest(
    payload: WeReadDigestBuildRequest,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    """Build a WeRead digest and optionally push it to Feishu."""
    service = WeReadDigestService()
    return await service.build_digest(
        start=payload.start,
        end=payload.end,
        source_names=payload.source_names,
        push_to_feishu=payload.push_to_feishu,
        open_id=payload.open_id,
        chat_id=payload.chat_id,
        redis=redis,
    )
