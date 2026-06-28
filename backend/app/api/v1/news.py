"""News aggregation API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_redis
from app.services.browser_news_digest import BrowserNewsDigestService
from app.services.feishu_bot import get_feishu_bot_service
from app.services.news_aggregator import NewsAggregationService
from app.services.news_push_history import NewsPushHistoryService
from app.services.weread_digest import WeReadDigestService
from app.tools.runtime_tools import ToolContext, registry

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
    mode: str = "aggregated_feed"
    generated_by: Optional[str] = None
    push_records: List["NewsDigestPushRecordResponse"] = Field(default_factory=list)


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
    status: str = "sent"
    receive_id_type: str
    receive_id: str
    target_hint: str
    message_id: Optional[str] = None
    record_id: Optional[str] = None
    pushed_at: Optional[str] = None
    error_detail: Optional[str] = None


class NewsDigestPushRecordResponse(BaseModel):
    id: str
    pushed_at: str
    title: str
    content: str = ""
    item_count: int
    status: str
    target_hint: str
    receive_id_type: str
    receive_id: str
    message_id: Optional[str] = None
    error_detail: Optional[str] = None


class BrowserNewsDigestWindowRequest(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class BrowserNewsDigestTopicRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=40)
    count: int = Field(default=0, ge=0)
    sources: List[str] = Field(default_factory=list)


class BrowserNewsDigestSourceRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=80)
    name: str = Field(..., min_length=1, max_length=80)
    homepage_url: Optional[str] = Field(default=None, max_length=2000)
    feed_url: Optional[str] = Field(default=None, max_length=2000)
    article_count: Optional[int] = Field(default=None, ge=0)
    status: str = Field(default="agent_submitted", max_length=20)
    last_error: Optional[str] = Field(default=None, max_length=500)
    fetched_at: Optional[datetime] = None


class BrowserNewsDigestItemRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    source_id: Optional[str] = Field(default=None, max_length=80)
    source_name: str = Field(..., min_length=1, max_length=80)
    url: str = Field(..., min_length=1, max_length=2000)
    published_at: Optional[datetime] = None
    summary: str = Field(..., min_length=1, max_length=500)
    highlights: List[str] = Field(default_factory=list, max_length=8)
    excerpt: Optional[str] = Field(default=None, max_length=1200)


class BrowserNewsDigestSubmitRequest(BaseModel):
    window: Optional[BrowserNewsDigestWindowRequest] = None
    topics: List[BrowserNewsDigestTopicRequest] = Field(default_factory=list)
    sources: List[BrowserNewsDigestSourceRequest] = Field(default_factory=list)
    items: List[BrowserNewsDigestItemRequest] = Field(default_factory=list, max_length=100)
    notes: List[str] = Field(default_factory=list, max_length=20)
    mode: str = Field(default="browser_agent", max_length=40)
    generated_by: str = Field(default="TRAE Work 资讯 Agent", max_length=80)


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


NewsDigestResponse.model_rebuild()


@router.get("/digest", response_model=NewsDigestResponse)
async def get_news_digest(
    refresh: bool = Query(False, description="Force refresh instead of using cached digest"),
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    """Get the latest completed daily news digest."""
    return await registry.invoke(
        "news.get_digest",
        context=ToolContext(redis=redis),
        args={"refresh": refresh},
    )


@router.post("/digest/refresh", response_model=NewsDigestResponse)
async def refresh_news_digest(redis: Any = Depends(get_redis)) -> dict[str, Any]:
    """Force rebuild the latest daily digest."""
    return await registry.invoke(
        "news.get_digest",
        context=ToolContext(redis=redis),
        args={"refresh": True},
    )


@router.post("/digest/push", response_model=NewsDigestPushResponse)
async def push_news_digest(
    payload: NewsDigestPushRequest,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    """Push a curated digest card to Feishu without exposing push token to browser."""
    aggregation_service = NewsAggregationService()
    push_history = NewsPushHistoryService()
    _, window_end = aggregation_service.get_latest_completed_window()
    bot = get_feishu_bot_service()
    if not bot.ready:
        record = await push_history.append_record(
            redis=redis,
            window_end=window_end,
            title=payload.title,
            content=payload.content,
            item_count=len(payload.items),
            status="failed",
            target_hint="Feishu bot not ready",
            receive_id_type="unavailable",
            receive_id=payload.chat_id or payload.open_id or "",
            error_detail="Feishu bot is not ready.",
        )
        return {
            "success": False,
            "status": "failed",
            "receive_id_type": record["receive_id_type"],
            "receive_id": record["receive_id"],
            "target_hint": record["target_hint"],
            "message_id": None,
            "record_id": record["id"],
            "pushed_at": record["pushed_at"],
            "error_detail": record["error_detail"],
        }

    try:
        result = await bot.push_news(
            title=payload.title,
            content=payload.content,
            items=[item.model_dump(exclude_none=True) for item in payload.items],
            open_id=payload.open_id,
            chat_id=payload.chat_id,
        )
    except HTTPException as exc:
        record = await push_history.append_record(
            redis=redis,
            window_end=window_end,
            title=payload.title,
            content=payload.content,
            item_count=len(payload.items),
            status="failed",
            target_hint="Feishu push failed",
            receive_id_type="unknown",
            receive_id=payload.chat_id or payload.open_id or "",
            error_detail=str(exc.detail),
        )
        return {
            "success": False,
            "status": "failed",
            "receive_id_type": record["receive_id_type"],
            "receive_id": record["receive_id"],
            "target_hint": record["target_hint"],
            "message_id": None,
            "record_id": record["id"],
            "pushed_at": record["pushed_at"],
            "error_detail": record["error_detail"],
        }

    record = await push_history.append_record(
        redis=redis,
        window_end=window_end,
        title=payload.title,
        content=payload.content,
        item_count=len(payload.items),
        status="sent",
        target_hint=result["target_hint"],
        receive_id_type=result["receive_id_type"],
        receive_id=result["receive_id"],
        message_id=result.get("message_id"),
    )
    return {
        "success": True,
        "status": "sent",
        **result,
        "record_id": record["id"],
        "pushed_at": record["pushed_at"],
        "error_detail": None,
    }


@router.post("/digest/submit", response_model=NewsDigestResponse)
async def submit_browser_news_digest(
    payload: BrowserNewsDigestSubmitRequest,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    """Accept a browser-agent produced digest snapshot for web display and later IM push."""
    service = BrowserNewsDigestService()
    push_history = NewsPushHistoryService()
    digest = await service.save_digest(redis=redis, payload=payload.model_dump(mode="json"))
    digest["push_records"] = await push_history.list_records(
        redis=redis,
        window_end=service.parse_window_end(digest),
    )
    return digest


@router.get("/sources", response_model=List[NewsSourceResponse])
async def get_news_sources() -> list[dict[str, Any]]:
    """List configured news sources."""
    items = await registry.invoke(
        "news.list_sources",
        context=ToolContext(),
        args={},
    )
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
        for item in items
    ]


@router.post("/weread/digest/build", response_model=WeReadDigestResponse)
async def build_weread_digest(
    payload: WeReadDigestBuildRequest,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    """Build a WeRead digest and optionally push it to Feishu."""
    service = WeReadDigestService()
    try:
        return await service.build_digest(
            start=payload.start,
            end=payload.end,
            source_names=payload.source_names,
            push_to_feishu=payload.push_to_feishu,
            open_id=payload.open_id,
            chat_id=payload.chat_id,
            redis=redis,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
