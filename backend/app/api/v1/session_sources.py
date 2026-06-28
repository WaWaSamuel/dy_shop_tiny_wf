"""External session source APIs."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_redis
from app.services.session_sources import SessionSourceService
from app.tools.runtime_tools import ToolContext, registry

router = APIRouter()


class SessionSourceProbeDetailResponse(BaseModel):
    display_name: Optional[str] = None
    user_vid: Optional[str] = None


class SessionSourceResponse(BaseModel):
    id: str
    name: str
    description: str
    homepage_url: str
    login_url: str
    domain_patterns: List[str] = Field(default_factory=list)
    project_keys: List[str] = Field(default_factory=list)
    auth_kind: str
    probe_kind: str
    probe_path: str
    cookie_key: str
    enabled: bool = True
    status: str
    severity: str
    healthy: bool
    message: str
    last_checked_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    supports_browser_sync: bool = True
    has_stored_cookie: bool = False
    is_stale: bool = False
    probe_detail: SessionSourceProbeDetailResponse = Field(default_factory=SessionSourceProbeDetailResponse)


class SessionSourceActionRequest(BaseModel):
    refresh_cookie_from_browser: bool = Field(default=False, description="Reload cookies from local browser first")


class SessionSourceCookieSyncRequest(BaseModel):
    cookie_header: str = Field(..., min_length=1, description="Raw Cookie header string copied from browser context")


@router.get("", response_model=List[SessionSourceResponse])
async def list_session_sources(
    refresh: bool = Query(False, description="Run a live probe before returning"),
    redis: Any = Depends(get_redis),
) -> list[dict[str, Any]]:
    return await registry.invoke(
        "session_sources.list",
        context=ToolContext(redis=redis),
        args={"refresh": refresh},
    )


@router.post("/{source_id}/probe", response_model=SessionSourceResponse)
async def probe_session_source(
    source_id: str,
    payload: SessionSourceActionRequest,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    return await registry.invoke(
        "session_sources.probe",
        context=ToolContext(redis=redis),
        args={
            "source_id": source_id,
            "refresh_cookie_from_browser": payload.refresh_cookie_from_browser,
        },
    )


@router.post("/{source_id}/reconnect", response_model=SessionSourceResponse)
async def reconnect_session_source(
    source_id: str,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    service = SessionSourceService()
    return await service.reconnect_source(redis=redis, source_id=source_id)


@router.post("/{source_id}/cookie-sync", response_model=SessionSourceResponse)
async def sync_session_source_cookie(
    source_id: str,
    payload: SessionSourceCookieSyncRequest,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    service = SessionSourceService()
    return await service.sync_cookie_header(
        redis=redis,
        source_id=source_id,
        cookie_header=payload.cookie_header,
    )


@router.post("/{source_id}/cookie-sync-plain", response_model=SessionSourceResponse)
async def sync_session_source_cookie_plain(
    source_id: str,
    request: Request,
    redis: Any = Depends(get_redis),
) -> dict[str, Any]:
    cookie_header = (await request.body()).decode("utf-8", errors="ignore")
    service = SessionSourceService()
    return await service.sync_cookie_header(
        redis=redis,
        source_id=source_id,
        cookie_header=cookie_header,
    )
