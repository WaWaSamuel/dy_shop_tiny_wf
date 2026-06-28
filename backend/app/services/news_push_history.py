"""Store news push history for web visibility."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.config import get_settings


class NewsPushHistoryService:
    """Persist news push records in Redis for frontend display."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.timezone = ZoneInfo(self.settings.NEWS_DIGEST_TIMEZONE)

    async def list_records(self, *, redis: Any, window_end: datetime) -> list[dict[str, Any]]:
        if redis is None:
            return []
        raw_records = await redis.lrange(self._records_key(window_end=window_end), 0, 19)
        records: list[dict[str, Any]] = []
        for raw in raw_records:
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    async def append_record(
        self,
        *,
        redis: Any,
        window_end: datetime,
        title: str,
        content: str | None,
        item_count: int,
        status: str,
        target_hint: str,
        receive_id_type: str,
        receive_id: str,
        message_id: str | None = None,
        error_detail: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": f"news_push_{uuid4().hex[:10]}",
            "pushed_at": datetime.now(self.timezone).isoformat(),
            "title": title,
            "content": content or "",
            "item_count": item_count,
            "status": status,
            "target_hint": target_hint,
            "receive_id_type": receive_id_type,
            "receive_id": receive_id,
            "message_id": message_id,
            "error_detail": error_detail,
        }
        if redis is None:
            return record

        key = self._records_key(window_end=window_end)
        await redis.lpush(key, json.dumps(record, ensure_ascii=False))
        await redis.ltrim(key, 0, 19)
        await redis.expire(key, self.settings.NEWS_DIGEST_CACHE_TTL_SECONDS)
        return record

    def _records_key(self, *, window_end: datetime) -> str:
        return f"news_digest_push_history:{window_end.astimezone(self.timezone).strftime('%Y%m%d%H')}"
