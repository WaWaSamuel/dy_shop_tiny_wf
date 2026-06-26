"""WeRead public-account digest service."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, ClassVar, Optional
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings, get_settings
from app.services.browser_cookie_provider import BrowserCookieProvider
from app.services.feishu_bot import get_feishu_bot_service
from app.services.session_sources import SessionSourceService

logger = logging.getLogger(__name__)

BOOK_ID_PATTERN = re.compile(r"MP_WXS_[A-Za-z0-9_]+")
OG_TITLE_PATTERN = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
MSG_LINK_PATTERN = re.compile(r'var\s+msg_link\s*=\s*"([^"]+)"', re.I)
JSON_MSG_LINK_PATTERN = re.compile(r'"msg_link"\s*:\s*"([^"]+)"', re.I)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?；;])")
SPACE_PATTERN = re.compile(r"[ \t\u3000]+")
BLANK_LINE_PATTERN = re.compile(r"\n{2,}")
READING_NOISE_PATTERN = re.compile(
    r".*?在小说阅读器读本章 去阅读 在小说阅读器中沉浸阅读",
    re.S,
)


@dataclass
class WeReadSource:
    id: str
    name: str
    book_id: str


class _VisibleTextExtractor(HTMLParser):
    """Extract visible text from article HTML."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag in {"br", "p", "div", "section", "article", "li", "h1", "h2", "h3", "blockquote"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "blockquote"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


class WeReadDigestService:
    """Collect WeRead public-account articles and render digest output."""

    _cookie_cache: ClassVar[tuple[float, str, httpx.Cookies] | None] = None

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.timezone = ZoneInfo(self.settings.WEREAD_DIGEST_TIMEZONE)
        self.request_timeout = self.settings.WEREAD_REQUEST_TIMEOUT_SECONDS
        self.repo_root = Path(__file__).resolve().parents[3]
        self.output_dir = Path(self.settings.WEREAD_MARKDOWN_OUTPUT_DIR).expanduser() if self.settings.WEREAD_MARKDOWN_OUTPUT_DIR else self.repo_root
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_provider = BrowserCookieProvider(settings=self.settings)

    async def build_digest(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        source_names: list[str] | None = None,
        push_to_feishu: bool = False,
        open_id: str | None = None,
        chat_id: str | None = None,
        redis: Any | None = None,
    ) -> dict[str, Any]:
        """Build the digest and optionally push it to Feishu."""
        window_start, window_end = self.resolve_window(start=start, end=end)
        cookie_header = await self._resolve_cookie_header(redis=redis)
        digest = await self._collect_digest(
            window_start=window_start,
            window_end=window_end,
            source_names=source_names or [],
            cookie_header=cookie_header,
        )
        markdown_path = self._write_markdown(digest)
        digest["markdown_file"] = str(markdown_path)

        if push_to_feishu:
            digest["push_result"] = await self._push_digest(
                digest=digest,
                open_id=open_id,
                chat_id=chat_id,
            )
        else:
            digest["push_result"] = None

        return digest

    def resolve_window(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        now: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        """Resolve digest window. Default is previous day 09:00 to current day 09:00."""
        if start and end:
            return self._ensure_local_dt(start), self._ensure_local_dt(end)

        current = self._ensure_local_dt(now or datetime.now(self.timezone))
        candidate_end = current.replace(
            hour=self.settings.WEREAD_DIGEST_WINDOW_END_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )
        if current < candidate_end:
            candidate_end -= timedelta(days=1)
        candidate_start = candidate_end - timedelta(days=1)
        return candidate_start, candidate_end

    async def _collect_digest(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        source_names: list[str],
        cookie_header: str,
    ) -> dict[str, Any]:
        cookies = self._load_cookies(cookie_header)
        headers = {
            "User-Agent": self.settings.NEWS_DIGEST_USER_AGENT,
            "Referer": "https://weread.qq.com/web/shelf",
            "Origin": "https://weread.qq.com",
        }

        async with httpx.AsyncClient(
            base_url="https://weread.qq.com",
            timeout=self.request_timeout,
            headers=headers,
            cookies=cookies,
            follow_redirects=True,
        ) as client:
            sources = await self._resolve_sources(client=client, source_names=source_names)
            source_payloads: list[dict[str, Any]] = []
            items: list[dict[str, Any]] = []
            notes: list[str] = []

            for source in sources:
                result = await self._collect_source_articles(
                    client=client,
                    source=source,
                    window_start=window_start,
                    window_end=window_end,
                )
                source_payloads.append(result["source"])
                items.extend(result["items"])
                if result.get("note"):
                    notes.append(result["note"])

        items.sort(key=lambda item: item["published_at"], reverse=True)
        items = items[: self.settings.WEREAD_MAX_ARTICLES]

        return {
            "window": self._serialize_window(window_start, window_end),
            "refreshed_at": datetime.now(self.timezone).isoformat(),
            "total_sources": len(source_payloads),
            "total_articles": len(items),
            "sources": source_payloads,
            "items": items,
            "notes": notes,
        }

    async def _resolve_sources(
        self,
        *,
        client: httpx.AsyncClient,
        source_names: list[str],
    ) -> list[WeReadSource]:
        configured = self._load_sources_from_config()
        if configured:
            sources = configured
        else:
            sources = await self._discover_sources_from_shelf(client)

        if not source_names:
            return sources

        wanted = {self._normalize_text(name) for name in source_names if name.strip()}
        filtered = [source for source in sources if self._normalize_text(source.name) in wanted]
        missing = sorted(wanted - {self._normalize_text(source.name) for source in filtered})
        if missing:
            logger.warning("Some WeRead sources were not found on shelf/config: %s", missing)
        return filtered

    def _load_sources_from_config(self) -> list[WeReadSource]:
        raw = (self.settings.WEREAD_SOURCE_CONFIG or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid WEREAD_SOURCE_CONFIG JSON: {exc}") from exc

        sources: list[WeReadSource] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            book_id = str(item.get("book_id") or item.get("bookId") or "").strip()
            if not book_id:
                continue
            name = str(item.get("name") or f"公众号 {index}").strip()
            source_id = str(item.get("id") or book_id).strip()
            sources.append(WeReadSource(id=source_id, name=name, book_id=book_id))
        return sources

    async def _discover_sources_from_shelf(self, client: httpx.AsyncClient) -> list[WeReadSource]:
        response = await client.get("/web/shelf")
        response.raise_for_status()
        book_ids = sorted(set(BOOK_ID_PATTERN.findall(response.text)))
        if not book_ids:
            raise RuntimeError("No WeRead public-account sources found on shelf. Check Chrome login status first.")

        sources: list[WeReadSource] = []
        for book_id in book_ids:
            book_info = await self._get_book_info(client, book_id)
            source_name = self._extract_book_title(book_info) or book_id
            sources.append(
                WeReadSource(
                    id=self._slugify(source_name) or book_id.lower(),
                    name=source_name,
                    book_id=book_id,
                )
            )
        return sources

    async def _get_book_info(self, client: httpx.AsyncClient, book_id: str) -> dict[str, Any]:
        for endpoint in ("/web/mp/cover", "/web/book/info"):
            response = await client.get(endpoint, params={"bookId": book_id})
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
        return {}

    async def _collect_source_articles(
        self,
        *,
        client: httpx.AsyncClient,
        source: WeReadSource,
        window_start: datetime,
        window_end: datetime,
    ) -> dict[str, Any]:
        offset = 0
        items: list[dict[str, Any]] = []
        note: str | None = None
        source_status = "ok"
        last_error: str | None = None

        try:
            while True:
                response = await client.get("/web/mp/articles", params={"bookId": source.book_id, "offset": offset})
                response.raise_for_status()
                data = response.json()
                reviews = self._extract_reviews(data)
                if not reviews:
                    break

                oldest_time: datetime | None = None
                for review_group in reviews:
                    group_time = self._extract_publish_time(review_group)
                    if group_time and (oldest_time is None or group_time < oldest_time):
                        oldest_time = group_time

                    sub_reviews = review_group.get("subReviews") or []
                    if not isinstance(sub_reviews, list):
                        continue

                    for sub_review in sub_reviews:
                        article = self._parse_article_stub(
                            source=source,
                            review_group=review_group,
                            sub_review=sub_review,
                        )
                        if article is None:
                            continue
                        if not (window_start <= article["published_dt"] < window_end):
                            continue

                        article_text, canonical_title, original_url = await self._fetch_article_text(
                            client=client,
                            review_id=article["review_id"],
                            fallback_title=article["title"],
                        )
                        article["title"] = canonical_title or article["title"]
                        if original_url:
                            article["url"] = original_url
                        article["summary"] = self._summarize_text(article_text or article["title"])
                        article["excerpt"] = self._trim_text(article_text, 220)
                        items.append(article)

                        if len(items) >= self.settings.WEREAD_MAX_ITEMS_PER_SOURCE:
                            break

                    if len(items) >= self.settings.WEREAD_MAX_ITEMS_PER_SOURCE:
                        break

                if len(items) >= self.settings.WEREAD_MAX_ITEMS_PER_SOURCE:
                    break
                if oldest_time and oldest_time < window_start:
                    break
                offset += len(reviews)
        except Exception as exc:
            source_status = "error"
            last_error = str(exc)
            note = f"{source.name} 抓取失败：{exc}"
            logger.warning("Failed to collect WeRead source %s: %s", source.name, exc)

        serialized_items = [self._serialize_item(item) for item in items]
        return {
            "source": {
                "id": source.id,
                "name": source.name,
                "book_id": source.book_id,
                "article_count": len(serialized_items),
                "status": source_status,
                "last_error": last_error,
            },
            "items": serialized_items,
            "note": note,
        }

    def _parse_article_stub(
        self,
        *,
        source: WeReadSource,
        review_group: dict[str, Any],
        sub_review: dict[str, Any],
    ) -> dict[str, Any] | None:
        review = sub_review.get("review") or {}
        mp_info = review.get("mpInfo") or {}
        review_id = self._pick_first(sub_review, review, keys=("reviewId", "review_id"))
        if not review_id:
            return None

        title = (
            self._pick_first(mp_info, review, sub_review, keys=("title", "name"))
            or f"{source.name} 文章 {review_id}"
        )
        published_dt = self._extract_publish_time(mp_info, review, sub_review, review_group)
        if published_dt is None:
            return None

        return {
            "id": hashlib.md5(f"{source.book_id}:{review_id}".encode("utf-8")).hexdigest(),
            "review_id": str(review_id),
            "title": str(title).strip(),
            "source_id": source.id,
            "source_name": source.name,
            "url": f"https://weread.qq.com/web/mp/content?reviewId={review_id}",
            "published_dt": published_dt,
        }

    async def _fetch_article_text(
        self,
        *,
        client: httpx.AsyncClient,
        review_id: str,
        fallback_title: str,
    ) -> tuple[str, str, str]:
        response = await client.get("/web/mp/content", params={"reviewId": review_id})
        response.raise_for_status()
        html = response.text
        title = self._extract_html_title(html) or fallback_title
        text = self._extract_html_text(html)
        original_url = self._extract_original_article_url(html)
        return self._trim_text(text, self.settings.WEREAD_ARTICLE_TEXT_LIMIT), title, original_url

    def _extract_html_title(self, html: str) -> str:
        for pattern in (OG_TITLE_PATTERN, TITLE_PATTERN):
            match = pattern.search(html)
            if match:
                return unescape(match.group(1)).strip()
        return ""

    def _extract_html_text(self, html: str) -> str:
        parser = _VisibleTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        text = unescape(text)
        text = SPACE_PATTERN.sub(" ", text)
        text = BLANK_LINE_PATTERN.sub("\n", text)
        lines = [line.strip() for line in text.splitlines()]
        cleaned_lines: list[str] = []
        for line in lines:
            if not line:
                continue
            if line in {"微信读书", "继续滑动看下一个", "轻触阅读原文"}:
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def _extract_original_article_url(self, html: str) -> str:
        for pattern in (MSG_LINK_PATTERN, JSON_MSG_LINK_PATTERN):
            match = pattern.search(html)
            if not match:
                continue
            candidate = match.group(1).strip()
            if not candidate:
                continue
            candidate = (
                candidate.replace("\\/", "/")
                .replace("\\x26", "&")
                .replace("&amp;", "&")
            )
            if candidate.startswith("https://mp.weixin.qq.com/"):
                return candidate
        return ""

    def _summarize_text(self, text: str) -> str:
        cleaned = self._trim_text(self._prepare_summary_text(text).replace("\r", "\n"), 400)
        if not cleaned:
            return "文章围绕该主题展开，建议打开原文查看完整内容。"

        sentences = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(cleaned) if part.strip()]
        for sentence in sentences:
            if len(sentence) < 18:
                continue
            if len(sentence) > 110:
                return sentence[:107].rstrip("，,；; ") + "。"
            if sentence.endswith(("。", "！", "？", "!", "?")):
                return sentence
            return sentence + "。"

        fallback = cleaned[:107].rstrip("，,；; ")
        return fallback + ("。" if fallback else "")

    def _prepare_summary_text(self, text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = READING_NOISE_PATTERN.sub("", cleaned)
        cleaned = cleaned.replace("在小说阅读器中沉浸阅读", " ")
        cleaned = cleaned.replace("在小说阅读器读本章 去阅读", " ")
        cleaned = BLANK_LINE_PATTERN.sub("\n", cleaned)
        cleaned = SPACE_PATTERN.sub(" ", cleaned)
        return cleaned.strip()

    async def _push_digest(
        self,
        *,
        digest: dict[str, Any],
        open_id: str | None,
        chat_id: str | None,
    ) -> dict[str, Any]:
        bot = get_feishu_bot_service()
        if not bot.ready:
            raise RuntimeError("Feishu bot is not ready.")

        items = [
            {
                "title": item["title"],
                "url": item["url"],
                "summary": item["summary"],
            }
            for item in digest.get("items", [])[:10]
        ]
        window = digest["window"]
        content = (
            f"时间范围：{window['start_label']} 到 {window['end_label']}\n"
            f"共 {digest['total_articles']} 篇，已按时间倒序整理。"
        )
        return await bot.push_news(
            title="微信读书公众号热点",
            content=content,
            items=items,
            open_id=open_id,
            chat_id=chat_id,
        )

    def _write_markdown(self, digest: dict[str, Any]) -> Path:
        start_label = digest["window"]["start_label"]
        end_label = digest["window"]["end_label"]
        file_name = f"weread_articles_{start_label}_to_{end_label}.md"
        output_path = self.output_dir / file_name

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in digest.get("items", []):
            grouped.setdefault(item["source_name"], []).append(item)

        lines = [
            "# 微信读书公众号文章汇总",
            "",
            f"时间范围：`{digest['window']['start_iso']}` 到 `{digest['window']['end_iso']}`",
            "",
            "说明：下列时间为微信读书目录里的推送时间；同一批多图文推送下的多篇文章，时间会相同。",
            "",
        ]

        for source_name in sorted(grouped.keys()):
            source_items = grouped[source_name]
            lines.append(f"## {source_name}")
            lines.append("")
            for item in source_items:
                lines.append(f"- {item['published_label']} | {item['title']}")
                lines.append(f"  [{item['summary']}]({item['url']})")
                lines.append("")
            lines.append(f"共 {len(source_items)} 篇。")
            lines.append("")

        lines.append(f"总计 {digest.get('total_articles', 0)} 篇。")
        output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output_path

    async def _resolve_cookie_header(self, *, redis: Any | None = None) -> str:
        if self.settings.WEREAD_COOKIE_HEADER.strip():
            return self.settings.WEREAD_COOKIE_HEADER.strip()
        if redis is not None:
            session_service = SessionSourceService(settings=self.settings)
            return await session_service.build_weread_cookie_header(redis=redis)
        return self.cookie_provider.cookie_header_from_chrome(domain_patterns=("weread.qq.com",))

    def _load_cookies(self, cookie_header: str) -> httpx.Cookies:
        now_ts = datetime.now().timestamp()
        cached = self.__class__._cookie_cache
        if cached and cached[1] == cookie_header and now_ts - cached[0] < self.settings.WEREAD_COOKIE_CACHE_TTL_SECONDS:
            return self._clone_cookies(cached[2])

        cookies = self._build_cookie_jar(cookie_header)
        self.__class__._cookie_cache = (now_ts, cookie_header, self._clone_cookies(cookies))
        return cookies

    def _build_cookie_jar(self, cookie_header: str) -> httpx.Cookies:
        return self.cookie_provider.build_cookie_jar(
            domain_patterns=("weread.qq.com",),
            cookie_header=cookie_header,
        )

    def _extract_reviews(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            reviews = data.get("reviews")
            if isinstance(reviews, list):
                return [item for item in reviews if isinstance(item, dict)]
            nested = data.get("data")
            if isinstance(nested, dict):
                reviews = nested.get("reviews")
                if isinstance(reviews, list):
                    return [item for item in reviews if isinstance(item, dict)]
        return []

    def _extract_publish_time(self, *payloads: dict[str, Any]) -> datetime | None:
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for key in ("time", "publishTime", "createTime", "ctime", "publish_time"):
                if key not in payload:
                    continue
                parsed = self._parse_timestamp(payload.get(key))
                if parsed is not None:
                    return parsed
            if "url" in payload and isinstance(payload["url"], str):
                query = parse_qs(urlparse(payload["url"]).query)
                if "ct" in query:
                    parsed = self._parse_timestamp(query["ct"][0])
                    if parsed is not None:
                        return parsed
        return None

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return self._ensure_local_dt(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.isdigit():
                value = int(stripped)
            else:
                try:
                    return self._ensure_local_dt(datetime.fromisoformat(stripped))
                except ValueError:
                    return None

        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=self.timezone)
        return None

    def _ensure_local_dt(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=self.timezone)
        return value.astimezone(self.timezone)

    def _extract_book_title(self, payload: dict[str, Any]) -> str:
        candidates = [
            payload.get("title"),
            payload.get("name"),
            (payload.get("bookInfo") or {}).get("title") if isinstance(payload.get("bookInfo"), dict) else None,
            (payload.get("bookInfo") or {}).get("name") if isinstance(payload.get("bookInfo"), dict) else None,
            (payload.get("book") or {}).get("title") if isinstance(payload.get("book"), dict) else None,
        ]
        for candidate in candidates:
            if candidate:
                return str(candidate).strip()
        return ""

    def _pick_first(self, *payloads: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for key in keys:
                value = payload.get(key)
                if value not in (None, ""):
                    return value
        return None

    def _serialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "review_id": item["review_id"],
            "title": item["title"],
            "source_id": item["source_id"],
            "source_name": item["source_name"],
            "url": item["url"],
            "published_at": item["published_dt"].isoformat(),
            "published_label": item["published_dt"].strftime("%Y-%m-%d %H:%M"),
            "summary": item["summary"],
            "excerpt": item["excerpt"],
        }

    def _serialize_window(self, start: datetime, end: datetime) -> dict[str, str]:
        return {
            "timezone": self.settings.WEREAD_DIGEST_TIMEZONE,
            "start_iso": start.isoformat(),
            "end_iso": end.isoformat(),
            "start_label": start.strftime("%Y-%m-%d_%H"),
            "end_label": end.strftime("%Y-%m-%d_%H"),
        }

    def _trim_text(self, text: str, limit: int) -> str:
        cleaned = SPACE_PATTERN.sub(" ", (text or "").strip())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: max(limit - 1, 0)].rstrip() + "…"

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", "", value).strip().lower()

    def _slugify(self, value: str) -> str:
        normalized = self._normalize_text(value)
        return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")

    def _clone_cookies(self, cookies: httpx.Cookies) -> httpx.Cookies:
        cloned = httpx.Cookies()
        for cookie in cookies.jar:
            cloned.set(cookie.name, cookie.value, domain=cookie.domain or "", path=cookie.path or "/")
        return cloned
