"""Feishu bot integration endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.feishu_bot import get_feishu_bot_service

router = APIRouter()
settings = get_settings()


class FeishuNewsItem(BaseModel):
    """Single news item rendered in the card."""

    title: str = Field(..., min_length=1, max_length=120)
    url: Optional[str] = Field(default=None, max_length=2000)
    summary: Optional[str] = Field(default=None, max_length=500)


class FeishuNewsPushRequest(BaseModel):
    """Request body for server-side news push."""

    title: str = Field(..., min_length=1, max_length=100)
    content: Optional[str] = Field(default=None, max_length=2000)
    items: list[FeishuNewsItem] = Field(default_factory=list, max_length=10)
    open_id: Optional[str] = Field(default=None, description="Optional target user open_id")
    chat_id: Optional[str] = Field(default=None, description="Optional target chat_id")


class FeishuOrderConfirmPushRequest(BaseModel):
    """Request body for order confirmation card push."""

    order_id: str = Field(..., min_length=1, max_length=80)
    open_id: Optional[str] = Field(default=None, description="Optional target user open_id")
    chat_id: Optional[str] = Field(default=None, description="Optional target chat_id")


@router.get("/status")
async def get_feishu_bot_status() -> dict:
    """Return Feishu bot runtime status."""
    bot = get_feishu_bot_service()
    bot_status = bot.status()
    return {
        "enabled": bot_status.enabled,
        "configured": bot_status.configured,
        "running": bot_status.running,
        "target_open_id_configured": bool(bot_status.target_open_id),
        "default_chat_id_configured": bool(bot_status.default_chat_id),
        "owner_id_configured": bool(bot_status.owner_id),
    }


@router.post("/news/push")
async def push_news(
    payload: FeishuNewsPushRequest,
    x_feishu_bot_token: Optional[str] = Header(default=None),
) -> dict:
    """Push a news message through the Feishu bot.

    This endpoint is intended for server-to-server usage. It is protected by a
    shared token to keep the current repo changes lightweight.
    """
    if not settings.FEISHU_BOT_PUSH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FEISHU_BOT_PUSH_TOKEN is not configured.",
        )
    if x_feishu_bot_token != settings.FEISHU_BOT_PUSH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Feishu bot push token.",
        )

    bot = get_feishu_bot_service()
    if not bot.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feishu bot is not ready.",
        )

    try:
        result = await bot.push_news(
            title=payload.title,
            content=payload.content,
            items=[item.model_dump(exclude_none=True) for item in payload.items],
            open_id=payload.open_id,
            chat_id=payload.chat_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Feishu push failed: {exc}",
        ) from exc

    return {
        "success": True,
        **result,
    }


@router.post("/orders/confirm/request")
async def push_order_confirmation(
    payload: FeishuOrderConfirmPushRequest,
    x_feishu_bot_token: Optional[str] = Header(default=None),
) -> dict:
    """Send an order confirmation card to the configured Feishu target."""
    if not settings.FEISHU_BOT_PUSH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FEISHU_BOT_PUSH_TOKEN is not configured.",
        )
    if x_feishu_bot_token != settings.FEISHU_BOT_PUSH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Feishu bot push token.",
        )

    bot = get_feishu_bot_service()
    if not bot.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feishu bot is not ready.",
        )

    try:
        reply = await bot.push_order_confirmation(
            order_ref=payload.order_id,
            chat_id=payload.chat_id,
            open_id=payload.open_id,
            reply_mode=False,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Feishu push failed: {exc}",
        ) from exc

    return {
        "success": True,
        "msg_type": reply.msg_type,
    }
