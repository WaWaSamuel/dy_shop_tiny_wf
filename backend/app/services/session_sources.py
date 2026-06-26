"""External session source registry and health checks."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable
from urllib.parse import unquote

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings
from app.services.browser_cookie_provider import BrowserCookieProvider


@dataclass(frozen=True)
class SessionSourceDefinition:
    id: str
    name: str
    description: str
    homepage_url: str
    login_url: str
    domain_patterns: tuple[str, ...]
    project_keys: tuple[str, ...] = field(default_factory=tuple)
    auth_kind: str = "cookie"
    probe_kind: str = "weread_user"
    probe_path: str = "/web/user"
    cookie_key: str = "wr_vid"
    enabled: bool = True


class SessionSourceService:
    """Manage browser-backed login state for external websites."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cookie_provider = BrowserCookieProvider(settings=self.settings)
        self._fernet = Fernet(self._build_fernet_key())
        self._definitions = {
            item.id: item
            for item in (
                SessionSourceDefinition(
                    id="weread",
                    name="微信读书",
                    description="用于公众号文章抓取、摘要整理和飞书热点推送。",
                    homepage_url="https://weread.qq.com/web/shelf",
                    login_url="https://weread.qq.com/web/shelf",
                    domain_patterns=("weread.qq.com",),
                    project_keys=("news",),
                    probe_kind="weread_user",
                    probe_path="/web/shelf",
                    cookie_key="wr_vid",
                ),
            )
        }

    def get_definition(self, source_id: str) -> SessionSourceDefinition:
        definition = self._definitions.get(source_id)
        if definition is None:
            raise KeyError(f"Unknown session source: {source_id}")
        return definition

    def definitions(self) -> list[SessionSourceDefinition]:
        return list(self._definitions.values())

    async def list_sources(
        self,
        *,
        redis: Any,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for definition in self.definitions():
            if refresh:
                items.append(await self.probe_source(redis=redis, source_id=definition.id))
                continue

            state = await self._read_state(redis=redis, source_id=definition.id)
            if state is None:
                items.append(self._default_payload(definition))
                continue
            items.append(self._compose_payload(definition, state))
        return items

    async def probe_source(
        self,
        *,
        redis: Any,
        source_id: str,
        refresh_cookie_from_browser: bool = False,
    ) -> dict[str, Any]:
        definition = self.get_definition(source_id)
        now = self._now_iso()
        error_message = ""
        cookie_header = await self._read_cookie(redis=redis, source_id=source_id)

        if refresh_cookie_from_browser or not cookie_header:
            try:
                cookie_header = self.cookie_provider.cookie_header_from_chrome(
                    domain_patterns=definition.domain_patterns,
                )
                await self._write_cookie(redis=redis, source_id=source_id, cookie_header=cookie_header)
            except Exception as exc:
                error_message = str(exc)
                cookie_header = cookie_header or ""

        if not cookie_header:
            state = {
                "status": "expired",
                "message": "未检测到可用登录态，请重新登录后同步。",
                "last_error": error_message or "No browser cookie available",
                "last_checked_at": now,
                "has_stored_cookie": False,
            }
            await self._write_state(redis=redis, source_id=source_id, state=state)
            return self._compose_payload(definition, state)

        try:
            result = await self._run_probe(definition=definition, cookie_header=cookie_header)
            state = {
                "status": "healthy",
                "message": result.get("message") or "登录态正常，可直接执行自动化任务。",
                "last_error": None,
                "last_checked_at": now,
                "last_success_at": now,
                "has_stored_cookie": True,
                "probe_detail": result,
            }
        except Exception as exc:
            if not refresh_cookie_from_browser:
                try:
                    refreshed_cookie = self.cookie_provider.cookie_header_from_chrome(
                        domain_patterns=definition.domain_patterns,
                    )
                    if refreshed_cookie and refreshed_cookie != cookie_header:
                        await self._write_cookie(redis=redis, source_id=source_id, cookie_header=refreshed_cookie)
                        result = await self._run_probe(definition=definition, cookie_header=refreshed_cookie)
                        state = {
                            "status": "healthy",
                            "message": result.get("message") or "已从浏览器刷新登录态。",
                            "last_error": None,
                            "last_checked_at": now,
                            "last_success_at": now,
                            "has_stored_cookie": True,
                            "probe_detail": result,
                        }
                        await self._write_state(redis=redis, source_id=source_id, state=state)
                        return self._compose_payload(definition, state)
                except Exception:
                    pass

            state = {
                "status": "expired",
                "message": "登录态失效，需要重新登录后同步。",
                "last_error": str(exc),
                "last_checked_at": now,
                "has_stored_cookie": bool(cookie_header),
            }

        await self._write_state(redis=redis, source_id=source_id, state=state)
        return self._compose_payload(definition, state)

    async def reconnect_source(self, *, redis: Any, source_id: str) -> dict[str, Any]:
        return await self.probe_source(
            redis=redis,
            source_id=source_id,
            refresh_cookie_from_browser=True,
        )

    async def sync_cookie_header(
        self,
        *,
        redis: Any,
        source_id: str,
        cookie_header: str,
    ) -> dict[str, Any]:
        cookie_header = cookie_header.strip()
        if not cookie_header:
            raise RuntimeError("cookie_header 不能为空。")
        await self._write_cookie(redis=redis, source_id=source_id, cookie_header=cookie_header)
        return await self.probe_source(
            redis=redis,
            source_id=source_id,
            refresh_cookie_from_browser=False,
        )

    async def run_scheduled_probe(self, *, redis: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for definition in self.definitions():
            results.append(
                await self.probe_source(
                    redis=redis,
                    source_id=definition.id,
                    refresh_cookie_from_browser=False,
                )
            )
        return results

    async def build_weread_cookie_header(self, *, redis: Any) -> str:
        definition = self.get_definition("weread")
        cookie_header = await self._read_cookie(redis=redis, source_id=definition.id)
        if cookie_header:
            return cookie_header

        cookie_header = self.settings.WEREAD_COOKIE_HEADER.strip()
        if cookie_header:
            return cookie_header

        cookie_header = self.cookie_provider.cookie_header_from_chrome(
            domain_patterns=definition.domain_patterns,
        )
        await self._write_cookie(redis=redis, source_id=definition.id, cookie_header=cookie_header)
        return cookie_header

    async def _run_probe(
        self,
        *,
        definition: SessionSourceDefinition,
        cookie_header: str,
    ) -> dict[str, Any]:
        cookies = self.cookie_provider.build_cookie_jar(
            domain_patterns=definition.domain_patterns,
            cookie_header=cookie_header,
        )
        headers = {
            "User-Agent": self.settings.NEWS_DIGEST_USER_AGENT,
            "Referer": definition.homepage_url,
            "Origin": self._origin_from_url(definition.homepage_url),
        }

        if definition.probe_kind == "weread_user":
            user_vid = self.cookie_provider.get_cookie_value(cookies, definition.cookie_key)
            if not user_vid:
                raise RuntimeError("缺少 wr_vid cookie，当前浏览器里的微信读书登录态不可用。")
            display_name = unquote(self.cookie_provider.get_cookie_value(cookies, "wr_name")).strip()
            async with httpx.AsyncClient(
                base_url=self._origin_from_url(definition.homepage_url),
                timeout=self.settings.SESSION_SOURCE_REQUEST_TIMEOUT_SECONDS,
                headers=headers,
                cookies=cookies,
                follow_redirects=True,
            ) as client:
                response = await client.get("/web/shelf")
                response.raise_for_status()
                html = response.text
                login_markers = ("扫码登录", "login_container", "登录后", "login-wrapper")
                if any(marker in html for marker in login_markers):
                    raise RuntimeError("微信读书返回了登录页，当前 cookie 已失效。")
                if "MP_WXS_" not in html and not display_name:
                    raise RuntimeError("微信读书书架页未识别到公众号内容，当前登录态校验未通过。")
                return {
                    "message": f"登录态正常，当前账号：{display_name or user_vid}",
                    "user_vid": user_vid,
                    "display_name": display_name,
                }
        raise RuntimeError(f"Unsupported probe kind: {definition.probe_kind}")

    async def _read_state(self, *, redis: Any, source_id: str) -> dict[str, Any] | None:
        raw = await redis.get(self._state_key(source_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def _write_state(self, *, redis: Any, source_id: str, state: dict[str, Any]) -> None:
        await redis.set(self._state_key(source_id), json.dumps(state, ensure_ascii=False))

    async def _read_cookie(self, *, redis: Any, source_id: str) -> str:
        encrypted = await redis.get(self._cookie_key(source_id))
        if not encrypted:
            return ""
        try:
            return self._fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    async def _write_cookie(self, *, redis: Any, source_id: str, cookie_header: str) -> None:
        token = self._fernet.encrypt(cookie_header.encode("utf-8")).decode("utf-8")
        await redis.set(self._cookie_key(source_id), token)

    def _compose_payload(self, definition: SessionSourceDefinition, state: dict[str, Any]) -> dict[str, Any]:
        status = state.get("status") or "unknown"
        last_checked_at = state.get("last_checked_at")
        is_stale = self._is_state_stale(last_checked_at)
        message = str(state.get("message") or self._default_message(status))
        if is_stale and status == "healthy":
            message = f"{message} 上次检查较早，建议重新探测。"

        return {
            **asdict(definition),
            "status": status,
            "severity": self._severity_from_status(status),
            "healthy": status == "healthy",
            "message": message,
            "last_checked_at": last_checked_at,
            "last_success_at": state.get("last_success_at"),
            "last_error": state.get("last_error"),
            "supports_browser_sync": True,
            "has_stored_cookie": bool(state.get("has_stored_cookie")),
            "is_stale": is_stale,
            "probe_detail": state.get("probe_detail") or {},
        }

    def _default_payload(self, definition: SessionSourceDefinition) -> dict[str, Any]:
        return {
            **asdict(definition),
            "status": "unknown",
            "severity": "warning",
            "healthy": False,
            "message": "尚未检查，请先执行一次连接检测。",
            "last_checked_at": None,
            "last_success_at": None,
            "last_error": None,
            "supports_browser_sync": True,
            "has_stored_cookie": False,
            "is_stale": True,
            "probe_detail": {},
        }

    def _default_message(self, status: str) -> str:
        if status == "healthy":
            return "登录态正常，可直接执行自动化任务。"
        if status == "expired":
            return "登录态失效，需要重新登录。"
        return "尚未检查。"

    def _severity_from_status(self, status: str) -> str:
        if status == "healthy":
            return "success"
        if status == "expired":
            return "danger"
        return "warning"

    def _is_state_stale(self, timestamp: str | None) -> bool:
        if not timestamp:
            return True
        try:
            checked_at = datetime.fromisoformat(timestamp)
        except ValueError:
            return True
        threshold = checked_at + timedelta(seconds=self.settings.SESSION_SOURCE_STATUS_STALE_SECONDS)
        return datetime.now(tz=checked_at.tzinfo) > threshold

    def _build_fernet_key(self) -> bytes:
        digest = hashlib.sha256(f"{self.settings.SECRET_KEY}:session-source-cookie".encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _state_key(self, source_id: str) -> str:
        return f"session-source:{source_id}:state"

    def _cookie_key(self, source_id: str) -> str:
        return f"session-source:{source_id}:cookie"

    def _origin_from_url(self, url: str) -> str:
        parts = url.split("/", 3)
        return "/".join(parts[:3])

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat()
