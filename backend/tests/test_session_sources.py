from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.services.session_sources import SessionSourceService


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str) -> None:
        self.data[key] = value


def test_list_sources_returns_unknown_before_probe() -> None:
    redis = FakeRedis()
    service = SessionSourceService(settings=Settings(SECRET_KEY="test-secret"))

    result = asyncio.run(service.list_sources(redis=redis, refresh=False))

    assert result[0]["id"] == "weread"
    assert result[0]["status"] == "unknown"
    assert result[0]["healthy"] is False


def test_probe_source_can_refresh_cookie_and_mark_healthy() -> None:
    redis = FakeRedis()
    service = SessionSourceService(settings=Settings(SECRET_KEY="test-secret"))

    service.cookie_provider.cookie_header_from_chrome = lambda **_: "wr_vid=fake-vid; wr_name=test"  # type: ignore[method-assign]

    async def fake_probe(*, definition, cookie_header: str):
        assert definition.id == "weread"
        assert "wr_vid=fake-vid" in cookie_header
        return {"message": "登录态正常，当前账号：测试账号", "display_name": "测试账号", "user_vid": "fake-vid"}

    service._run_probe = fake_probe  # type: ignore[method-assign]

    result = asyncio.run(service.reconnect_source(redis=redis, source_id="weread"))

    assert result["status"] == "healthy"
    assert result["healthy"] is True
    assert result["probe_detail"]["display_name"] == "测试账号"
    assert result["has_stored_cookie"] is True


def test_probe_source_marks_expired_without_cookie() -> None:
    redis = FakeRedis()
    service = SessionSourceService(settings=Settings(SECRET_KEY="test-secret"))

    def fail_cookie_refresh(**_):
        raise RuntimeError("没有找到微信读书 cookie")

    service.cookie_provider.cookie_header_from_chrome = fail_cookie_refresh  # type: ignore[method-assign]

    result = asyncio.run(service.probe_source(redis=redis, source_id="weread"))

    assert result["status"] == "expired"
    assert result["healthy"] is False
    assert "重新登录" in result["message"]
