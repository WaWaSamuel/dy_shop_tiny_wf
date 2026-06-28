#!/usr/bin/env python3
"""Append one agent jump log to the local JSONL queue."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOG_PATH = REPO_ROOT / ".trae" / "runtime" / "agents-log.jsonl"
ALLOWED_EVENT_TYPES = {"jump", "handoff", "reroute"}


def _text(payload: dict[str, Any], key: str, *, required: bool = False) -> str | None:
    value = str(payload.get(key) or "").strip()
    if required and not value:
        raise ValueError(f"agents.log 缺少 {key}")
    return value or None


def _load_payload(raw_payload: str | None) -> dict[str, Any]:
    if not raw_payload:
        return {}
    data = json.loads(raw_payload)
    if not isinstance(data, dict):
        raise ValueError("--payload 必须是 JSON object")
    return data


def build_record(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = _text(payload, "event_type") or "jump"
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError("event_type 只能是 jump / handoff / reroute")

    from_agent = _text(payload, "from_agent", required=True)
    to_agent = _text(payload, "to_agent", required=True)
    reason = _text(payload, "reason", required=True)
    created_at = datetime.now(timezone.utc).isoformat()
    run_id = _text(payload, "run_id") or f"agents-log:{uuid4()}"
    local_log_id = _text(payload, "local_log_id") or str(uuid4())

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    record = {
        "schema_version": 1,
        "local_log_id": local_log_id,
        "project_key": _text(payload, "project_key") or "dyshop",
        "event_type": event_type,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "from_workflow": _text(payload, "from_workflow"),
        "to_workflow": _text(payload, "to_workflow"),
        "trigger": _text(payload, "trigger"),
        "reason": reason,
        "handoff_summary": _text(payload, "handoff_summary"),
        "run_id": run_id,
        "parent_run_id": _text(payload, "parent_run_id"),
        "level": _text(payload, "level") or "info",
        "metadata": metadata,
        "created_at": created_at,
    }
    return {key: value for key, value in record.items() if value is not None}


def append_record(record: dict[str, Any], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        file.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one agent jump log to local JSONL.")
    parser.add_argument("--payload", help="JSON object payload. CLI flags override payload keys.")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="Target JSONL path.")
    parser.add_argument("--event-type", choices=sorted(ALLOWED_EVENT_TYPES))
    parser.add_argument("--from-agent")
    parser.add_argument("--to-agent")
    parser.add_argument("--from-workflow")
    parser.add_argument("--to-workflow")
    parser.add_argument("--trigger")
    parser.add_argument("--reason")
    parser.add_argument("--handoff-summary")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    payload = _load_payload(args.payload)
    flag_map = {
        "event_type": args.event_type,
        "from_agent": args.from_agent,
        "to_agent": args.to_agent,
        "from_workflow": args.from_workflow,
        "to_workflow": args.to_workflow,
        "trigger": args.trigger,
        "reason": args.reason,
        "handoff_summary": args.handoff_summary,
        "run_id": args.run_id,
    }
    payload.update({key: value for key, value in flag_map.items() if value is not None})

    record = build_record(payload)
    log_path = Path(args.log_path).expanduser()
    if not log_path.is_absolute():
        log_path = REPO_ROOT / log_path
    append_record(record, log_path)
    print(json.dumps({"ok": True, "log_path": str(log_path), **record}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
