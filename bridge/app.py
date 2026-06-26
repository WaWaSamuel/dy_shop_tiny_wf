"""Host-side bridge service for syncing browser cookies back to the backend."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException

from bridge.config import BridgeSettings
from bridge.services.browser_cookie_provider import BrowserCookieProvider
from bridge.services.session_sources import get_definition, list_sources


@lru_cache()
def get_settings() -> BridgeSettings:
    return BridgeSettings.from_env()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DYShop Session Bridge",
        version="0.1.0",
        description="Read host Chrome cookies and sync them to the Docker backend.",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "backend_api_base_url": settings.backend_api_base_url,
            "chrome_profile_name": settings.chrome_profile_name,
            "sources": list_sources(),
        }

    @app.get("/sources")
    async def sources() -> dict[str, Any]:
        return {"items": list_sources()}

    @app.post("/sync/{source_id}")
    async def sync_source(source_id: str) -> dict[str, Any]:
        try:
            definition = get_definition(source_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        provider = BrowserCookieProvider(settings=settings)
        try:
            cookie_header = provider.cookie_header_from_chrome(
                domain_patterns=definition.domain_patterns,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Failed to read browser cookies: {exc}") from exc

        endpoint = f"{settings.backend_api_base_url.rstrip('/')}/session-sources/{source_id}/cookie-sync"
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(endpoint, json={"cookie_header": cookie_header})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or exc.response.reason_phrase
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Backend sync unavailable: {exc}") from exc

    return app


app = create_app()
