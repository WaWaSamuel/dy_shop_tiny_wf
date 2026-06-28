"""Store browser-driven news digest snapshots for web visibility."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings


class BrowserNewsDigestService:
    """Persist browser-agent produced digest snapshots in Redis."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.timezone = ZoneInfo(self.settings.NEWS_DIGEST_TIMEZONE)

    async def get_latest_digest(self, *, redis: Any) -> dict[str, Any] | None:
        if redis is None:
            return None
        latest_key = await redis.get(self._latest_key())
        if not latest_key:
            return None
        raw = await redis.get(latest_key)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    async def save_digest(
        self,
        *,
        redis: Any,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        digest = self._normalize_digest(payload)
        if redis is None:
            return digest

        key = self._digest_key(window_end=digest["window"]["end"])
        serialized = json.dumps(digest, ensure_ascii=False)
        await redis.setex(key, self.settings.NEWS_DIGEST_CACHE_TTL_SECONDS, serialized)
        await redis.setex(self._latest_key(), self.settings.NEWS_DIGEST_CACHE_TTL_SECONDS, key)
        return digest

    def resolve_window(self, *, start: str | None = None, end: str | None = None) -> dict[str, str]:
        now = datetime.now(self.timezone)
        window_end = self._parse_datetime(end) if end else now
        window_start = self._parse_datetime(start) if start else (window_end - timedelta(hours=24))
        return {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "timezone": self.settings.NEWS_DIGEST_TIMEZONE,
            "label": f"{window_start.strftime('%m-%d %H:%M')} - {window_end.strftime('%m-%d %H:%M')}",
        }

    def parse_window_end(self, digest: dict[str, Any]) -> datetime:
        return self._parse_datetime(digest.get("window", {}).get("end"))

    def _normalize_digest(self, payload: dict[str, Any]) -> dict[str, Any]:
        window_payload = payload.get("window") if isinstance(payload.get("window"), dict) else {}
        window = self.resolve_window(
            start=window_payload.get("start"),
            end=window_payload.get("end"),
        )

        items = [self._normalize_item(index, item) for index, item in enumerate(payload.get("items") or [], start=1)]
        sources = self._normalize_sources(payload.get("sources") or [], items)
        topics = self._normalize_topics(payload.get("topics") or [], items)
        notes = [str(note).strip() for note in (payload.get("notes") or []) if str(note).strip()]
        mode = str(payload.get("mode") or "browser_agent").strip() or "browser_agent"
        generated_by = str(payload.get("generated_by") or "TRAE Work 资讯 Agent").strip() or "TRAE Work 资讯 Agent"

        return {
            "window": window,
            "refreshed_at": datetime.now(self.timezone).isoformat(),
            "total_sources": len(sources),
            "total_articles": len(items),
            "topics": topics,
            "sources": sources,
            "items": items,
            "notes": notes,
            "mode": mode,
            "generated_by": generated_by,
        }

    def _normalize_item(self, index: int, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            item = {}
        published_at = self._parse_datetime(item.get("published_at")).isoformat()
        source_name = str(item.get("source_name") or "未命名来源").strip() or "未命名来源"
        source_id = str(item.get("source_id") or self._slugify(source_name) or f"source_{index}").strip()
        highlights = [str(value).strip() for value in (item.get("highlights") or []) if str(value).strip()]
        return {
            "id": str(item.get("id") or f"browser_news_{index}").strip(),
            "title": str(item.get("title") or "未命名文章").strip() or "未命名文章",
            "source_id": source_id,
            "source_name": source_name,
            "url": str(item.get("url") or "").strip(),
            "published_at": published_at,
            "summary": str(item.get("summary") or "").strip(),
            "highlights": highlights[:5],
            "excerpt": str(item.get("excerpt") or "").strip(),
        }

    def _normalize_sources(self, source_payloads: list[Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counters = Counter(item["source_id"] for item in items)
        names = {item["source_id"]: item["source_name"] for item in items}
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()

        for raw in source_payloads:
            if not isinstance(raw, dict):
                continue
            source_name = str(raw.get("name") or raw.get("source_name") or "未命名来源").strip() or "未命名来源"
            source_id = str(raw.get("id") or raw.get("source_id") or self._slugify(source_name)).strip()
            if not source_id or source_id in seen:
                continue
            normalized.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "feed_url": str(raw.get("feed_url") or raw.get("homepage_url") or "https://weread.qq.com/web/shelf").strip(),
                    "homepage_url": str(raw.get("homepage_url") or raw.get("feed_url") or "https://weread.qq.com/web/shelf").strip(),
                    "article_count": int(raw.get("article_count") or counters.get(source_id, 0)),
                    "status": str(raw.get("status") or "agent_submitted"),
                    "last_error": raw.get("last_error"),
                    "fetched_at": str(raw.get("fetched_at") or datetime.now(self.timezone).isoformat()),
                }
            )
            seen.add(source_id)

        for source_id, count in counters.items():
            if source_id in seen:
                continue
            source_name = names.get(source_id) or source_id
            normalized.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "feed_url": "https://weread.qq.com/web/shelf",
                    "homepage_url": "https://weread.qq.com/web/shelf",
                    "article_count": count,
                    "status": "agent_submitted",
                    "last_error": None,
                    "fetched_at": datetime.now(self.timezone).isoformat(),
                }
            )
        return normalized

    def _normalize_topics(self, topic_payloads: list[Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in topic_payloads:
            if not isinstance(raw, dict):
                continue
            topic = str(raw.get("topic") or "").strip()
            if not topic:
                continue
            normalized.append(
                {
                    "topic": topic,
                    "count": int(raw.get("count") or 0),
                    "sources": [str(value).strip() for value in (raw.get("sources") or []) if str(value).strip()],
                }
            )
        if normalized:
            return normalized

        topic_index: dict[str, dict[str, Any]] = {}
        for item in items:
            for highlight in item.get("highlights") or []:
                topic = str(highlight).strip()
                if not topic:
                    continue
                bucket = topic_index.setdefault(topic, {"topic": topic, "count": 0, "sources": set()})
                bucket["count"] += 1
                bucket["sources"].add(item["source_name"])
        result = [
            {
                "topic": topic,
                "count": data["count"],
                "sources": sorted(data["sources"]),
            }
            for topic, data in topic_index.items()
        ]
        result.sort(key=lambda item: (-item["count"], item["topic"]))
        return result[:8]

    def _digest_key(self, *, window_end: str) -> str:
        parsed = self._parse_datetime(window_end)
        return f"browser_news_digest:{parsed.astimezone(self.timezone).strftime('%Y%m%d%H%M')}"

    @staticmethod
    def _latest_key() -> str:
        return "browser_news_digest:latest"

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(self.timezone) if value.tzinfo else value.replace(tzinfo=self.timezone)
        raw = str(value or "").strip()
        if not raw:
            return datetime.now(self.timezone)
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(self.timezone)
            parsed = datetime.fromisoformat(raw)
            return parsed.astimezone(self.timezone) if parsed.tzinfo else parsed.replace(tzinfo=self.timezone)
        except ValueError:
            return datetime.now(self.timezone)

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
        return "_".join(part for part in cleaned.split("_") if part)
