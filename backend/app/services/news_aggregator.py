"""News digest aggregation service.

This service builds a daily digest for the latest completed overnight window
(default: previous day 21:00 -> current day 09:00, Asia/Shanghai).

Practical constraint:
- There is no stable public API for reading a user's followed WeChat official
  account list directly.
- This implementation therefore works from a configured source list
  (for example RSSHub feeds or other RSS/Atom/JSON feeds that mirror the
  target public accounts/articles).
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

WECHAT_CONTENT_PATTERN = re.compile(
    r'(?is)<(?:div|section)[^>]+id=["\']js_content["\'][^>]*>(.*?)</(?:div|section)>'
)
HTML_TAG_PATTERN = re.compile(r"(?is)<[^>]+>")
SCRIPT_STYLE_PATTERN = re.compile(r"(?is)<(script|style).*?>.*?</\\1>")
MULTI_SPACE_PATTERN = re.compile(r"[ \t\u3000]+")
MULTI_LINE_PATTERN = re.compile(r"\n{2,}")

STOPWORDS = {
    "我们", "你们", "他们", "这个", "那个", "已经", "因为", "所以", "一个", "一种",
    "进行", "需要", "通过", "相关", "当前", "今天", "昨日", "如果", "以及", "内容",
    "消息", "信息", "文章", "公众号", "官方", "时候", "可以", "还是", "这里", "就是",
    "进行中", "摘要", "来源", "来源于", "发布", "更新", "查看", "了解", "点击", "更多",
    "http", "https", "wechat", "mp", "com", "www",
}


class NewsAggregationService:
    """Aggregate configured news sources into a structured digest."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.timezone = ZoneInfo(self.settings.NEWS_DIGEST_TIMEZONE)
        self.request_timeout = self.settings.NEWS_DIGEST_REQUEST_TIMEOUT_SECONDS

    async def get_digest(
        self,
        *,
        redis: Any | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return cached or freshly built digest."""
        window_start, window_end = self.get_latest_completed_window()
        cache_key = self._cache_key(window_end=window_end)

        if redis is not None and not force_refresh:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

        digest = await self._build_digest(window_start=window_start, window_end=window_end)

        if redis is not None:
            await redis.setex(
                cache_key,
                self.settings.NEWS_DIGEST_CACHE_TTL_SECONDS,
                json.dumps(digest, ensure_ascii=False),
            )
        return digest

    def get_sources(self) -> list[dict[str, Any]]:
        """Return configured sources for frontend display."""
        return [source for source in self._load_sources()]

    def get_latest_completed_window(self, now: datetime | None = None) -> tuple[datetime, datetime]:
        """Return the latest fully completed digest window in local timezone."""
        current = now.astimezone(self.timezone) if now and now.tzinfo else datetime.now(self.timezone)
        candidate_end = current.replace(
            hour=self.settings.NEWS_DIGEST_WINDOW_END_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )
        if current < candidate_end:
            candidate_end -= timedelta(days=1)

        hours = self._window_span_hours()
        window_start = candidate_end - timedelta(hours=hours)
        return window_start, candidate_end

    async def _build_digest(self, *, window_start: datetime, window_end: datetime) -> dict[str, Any]:
        sources = self._load_sources()
        if not sources:
            return {
                "window": self._serialize_window(window_start, window_end),
                "refreshed_at": datetime.now(self.timezone).isoformat(),
                "total_sources": 0,
                "total_articles": 0,
                "topics": [],
                "sources": [],
                "items": [],
                "notes": [
                    "尚未配置公众号源。请在 NEWS_SOURCE_CONFIG 中配置 feed_url 列表。",
                    "建议使用 RSSHub 或其它可稳定访问的 RSS/Atom/JSON Feed 作为公众号镜像源。",
                ],
            }

        headers = {"User-Agent": self.settings.NEWS_DIGEST_USER_AGENT}
        source_payloads: list[dict[str, Any]] = []
        article_items: list[dict[str, Any]] = []
        notes: list[str] = []

        async with httpx.AsyncClient(timeout=self.request_timeout, headers=headers, follow_redirects=True) as client:
            for source in sources:
                source_result = await self._collect_source_articles(
                    client=client,
                    source=source,
                    window_start=window_start,
                    window_end=window_end,
                )
                source_payloads.append(source_result["source"])
                article_items.extend(source_result["items"])
                if source_result.get("note"):
                    notes.append(source_result["note"])

        article_items.sort(key=lambda item: item["published_at"], reverse=True)
        article_items = article_items[: self.settings.NEWS_DIGEST_MAX_ARTICLES]

        return {
            "window": self._serialize_window(window_start, window_end),
            "refreshed_at": datetime.now(self.timezone).isoformat(),
            "total_sources": len(source_payloads),
            "total_articles": len(article_items),
            "topics": self._extract_topics(article_items),
            "sources": source_payloads,
            "items": article_items,
            "notes": notes,
        }

    async def _collect_source_articles(
        self,
        *,
        client: httpx.AsyncClient,
        source: dict[str, Any],
        window_start: datetime,
        window_end: datetime,
    ) -> dict[str, Any]:
        try:
            response = await client.get(source["feed_url"])
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch news source %s: %s", source["name"], exc)
            return {
                "source": {
                    "id": source["id"],
                    "name": source["name"],
                    "feed_url": source["feed_url"],
                    "homepage_url": source.get("homepage_url"),
                    "article_count": 0,
                    "status": "error",
                    "last_error": str(exc),
                    "fetched_at": datetime.now(self.timezone).isoformat(),
                },
                "items": [],
                "note": f"{source['name']} 抓取失败：{exc}",
            }

        entries = self._parse_feed(response.text)
        items: list[dict[str, Any]] = []

        for entry in entries:
            published_at = self._parse_datetime(entry.get("published_at"))
            if published_at is None:
                continue
            local_time = published_at.astimezone(self.timezone)
            if not (window_start <= local_time <= window_end):
                continue

            article_text = await self._fetch_article_text(client, entry.get("url") or "")
            source_text = article_text or entry.get("summary") or entry.get("title") or ""
            summary, highlights = self._summarize_text(source_text)

            items.append(
                {
                    "id": self._article_id(source["id"], entry.get("url") or entry.get("title") or ""),
                    "title": entry.get("title") or "未命名文章",
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "url": entry.get("url") or source.get("homepage_url") or source["feed_url"],
                    "published_at": local_time.isoformat(),
                    "summary": summary,
                    "highlights": highlights,
                    "excerpt": self._trim_text(source_text, 220),
                }
            )
            if len(items) >= self.settings.NEWS_DIGEST_MAX_ITEMS_PER_SOURCE:
                break

        return {
            "source": {
                "id": source["id"],
                "name": source["name"],
                "feed_url": source["feed_url"],
                "homepage_url": source.get("homepage_url"),
                "article_count": len(items),
                "status": "ok",
                "last_error": None,
                "fetched_at": datetime.now(self.timezone).isoformat(),
            },
            "items": items,
        }

    def _load_sources(self) -> list[dict[str, Any]]:
        raw = (self.settings.NEWS_SOURCE_CONFIG or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid NEWS_SOURCE_CONFIG JSON: %s", exc)
            return []

        sources: list[dict[str, Any]] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            if item.get("enabled", True) is False:
                continue
            feed_url = item.get("feed_url") or item.get("rss_url")
            if not feed_url:
                continue
            sources.append(
                {
                    "id": item.get("id") or f"source_{index + 1}",
                    "name": item.get("name") or f"公众号源 {index + 1}",
                    "feed_url": feed_url,
                    "homepage_url": item.get("homepage_url") or "",
                }
            )
        return sources

    def _parse_feed(self, payload: str) -> list[dict[str, str]]:
        text = payload.strip()
        if not text:
            return []
        if text.startswith("{") or text.startswith("["):
            return self._parse_json_feed(text)
        return self._parse_xml_feed(text)

    def _parse_json_feed(self, payload: str) -> list[dict[str, str]]:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        items = data.get("items", data if isinstance(data, list) else [])
        parsed: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            parsed.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or item.get("external_url") or ""),
                    "published_at": str(
                        item.get("date_published")
                        or item.get("published_at")
                        or item.get("published")
                        or ""
                    ),
                    "summary": str(item.get("summary") or item.get("content_text") or item.get("description") or ""),
                }
            )
        return parsed

    def _parse_xml_feed(self, payload: str) -> list[dict[str, str]]:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []

        entries = root.findall(".//item")
        if not entries:
            entries = root.findall(".//{*}entry")

        parsed: list[dict[str, str]] = []
        for entry in entries:
            link = self._find_link(entry)
            parsed.append(
                {
                    "title": self._find_text(entry, {"title"}),
                    "url": link,
                    "published_at": self._find_text(entry, {"pubDate", "published", "updated", "date"}),
                    "summary": self._find_text(entry, {"description", "summary", "content", "encoded"}),
                }
            )
        return parsed

    def _find_text(self, node: ET.Element, candidates: set[str]) -> str:
        for child in node.iter():
            local_name = child.tag.split("}")[-1]
            if local_name in candidates:
                text = "".join(child.itertext()).strip()
                if text:
                    return text
        return ""

    def _find_link(self, node: ET.Element) -> str:
        for child in node.iter():
            local_name = child.tag.split("}")[-1]
            if local_name != "link":
                continue
            href = child.attrib.get("href")
            if href:
                return href.strip()
            text = "".join(child.itertext()).strip()
            if text:
                return text
        return ""

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=self.timezone)
            return parsed
        except ValueError:
            pass

        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=self.timezone)
            return parsed
        except (TypeError, ValueError):
            return None

    async def _fetch_article_text(self, client: httpx.AsyncClient, url: str) -> str:
        if not url:
            return ""
        try:
            response = await client.get(url)
            response.raise_for_status()
        except Exception:
            return ""

        html = response.text
        if not html:
            return ""

        content_match = WECHAT_CONTENT_PATTERN.search(html)
        candidate = content_match.group(1) if content_match else html
        candidate = SCRIPT_STYLE_PATTERN.sub(" ", candidate)
        candidate = re.sub(r"(?i)<br\\s*/?>", "\n", candidate)
        candidate = re.sub(r"(?i)</p>", "\n", candidate)
        text = HTML_TAG_PATTERN.sub(" ", candidate)
        text = unescape(text)
        text = MULTI_SPACE_PATTERN.sub(" ", text)
        text = MULTI_LINE_PATTERN.sub("\n", text)
        return self._trim_text(text.strip(), self.settings.NEWS_DIGEST_ARTICLE_TEXT_LIMIT)

    def _summarize_text(self, text: str) -> tuple[str, list[str]]:
        normalized = self._normalize_text(text)
        if not normalized:
            return "暂无可提炼摘要。", []

        parts = [part.strip() for part in re.split(r"[。！？!?；;\n]", normalized) if len(part.strip()) >= 8]
        if not parts:
            return self._trim_text(normalized, 120), []

        highlights = parts[:3]
        summary = "；".join(highlights)
        return self._trim_text(summary, 160), [self._trim_text(item, 36) for item in highlights[:3]]

    def _extract_topics(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        topic_sources: dict[str, set[str]] = {}
        for item in items:
            corpus = f"{item.get('title', '')} {item.get('summary', '')}"
            tokens = self._extract_keywords(corpus)
            seen: set[str] = set()
            for token in tokens:
                if token in seen:
                    continue
                seen.add(token)
                counter[token] += 1
                topic_sources.setdefault(token, set()).add(item.get("source_name", ""))

        topics = []
        for topic, count in counter.most_common(8):
            topics.append(
                {
                    "topic": topic,
                    "count": count,
                    "sources": sorted(source for source in topic_sources.get(topic, set()) if source),
                }
            )
        return topics

    def _extract_keywords(self, text: str) -> list[str]:
        normalized = self._normalize_text(text)
        chinese_tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", normalized)
        ascii_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", normalized)
        keywords = []
        for token in [*chinese_tokens, *ascii_tokens]:
            cleaned = token.strip().lower()
            if cleaned in STOPWORDS or len(cleaned) < 2:
                continue
            keywords.append(cleaned)
        return keywords

    def _normalize_text(self, text: str) -> str:
        return MULTI_SPACE_PATTERN.sub(" ", unescape(text or "")).strip()

    def _serialize_window(self, start: datetime, end: datetime) -> dict[str, Any]:
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": self.settings.NEWS_DIGEST_TIMEZONE,
            "label": f"{start.strftime('%m-%d %H:%M')} - {end.strftime('%m-%d %H:%M')}",
        }

    def _window_span_hours(self) -> int:
        start = self.settings.NEWS_DIGEST_WINDOW_START_HOUR
        end = self.settings.NEWS_DIGEST_WINDOW_END_HOUR
        return (24 - start + end) if start >= end else (end - start)

    def _cache_key(self, *, window_end: datetime) -> str:
        return f"news:digest:{window_end.strftime('%Y%m%d%H')}"

    def _article_id(self, source_id: str, identifier: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9]+", "-", identifier.strip().lower()).strip("-")
        return f"{source_id}:{safe[:80] or 'article'}"

    def _trim_text(self, value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[: max(limit - 1, 1)].rstrip() + "…"
