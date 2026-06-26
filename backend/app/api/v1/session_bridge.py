"""Proxy session sync requests to the host-side bridge service."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter()


@router.post("/sync/{source_id}")
async def sync_session_via_host_bridge(source_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.SESSION_BRIDGE_ENABLED:
        raise HTTPException(status_code=503, detail="Session bridge is disabled")

    endpoint = f"{settings.SESSION_BRIDGE_BASE_URL.rstrip('/')}/sync/{source_id}"
    try:
        async with httpx.AsyncClient(timeout=settings.SESSION_BRIDGE_TIMEOUT_SECONDS) as client:
            response = await client.post(endpoint)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Session bridge unavailable: {exc}") from exc
