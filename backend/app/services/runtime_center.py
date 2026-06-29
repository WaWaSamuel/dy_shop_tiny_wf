"""Runtime execution center: schema bootstrap, catalog discovery and log queries."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

def _discover_repo_root() -> Path:
    """Find the project root from both local and container paths."""
    current_file = Path(__file__).resolve()
    for candidate in [current_file.parent, *current_file.parents]:
        if (candidate / ".trae").exists():
            return candidate
    return current_file.parents[2]


REPO_ROOT = _discover_repo_root()
TRAE_ROOT = REPO_ROOT / ".trae"
LOCAL_AGENTS_LOG_PATH = TRAE_ROOT / "runtime" / "agents-log.jsonl"

SCHEMA_STATEMENTS = [
    """
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp"
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_execution_records (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        owner_id TEXT NOT NULL,
        project_key TEXT NOT NULL DEFAULT 'dyshop',
        workflow_id TEXT NULL,
        run_id TEXT NOT NULL,
        parent_run_id TEXT NULL,
        capability_kind TEXT NOT NULL,
        capability_key TEXT NOT NULL,
        capability_label TEXT NULL,
        source_kind TEXT NULL,
        source_key TEXT NULL,
        phase TEXT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        level TEXT NOT NULL DEFAULT 'info',
        title TEXT NOT NULL,
        summary TEXT NULL,
        detail TEXT NULL,
        host_issue TEXT NULL,
        review_scorecard JSONB NOT NULL DEFAULT '{}'::jsonb,
        input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        loop_round INTEGER NULL,
        started_at TIMESTAMPTZ NULL,
        finished_at TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_runtime_execution_records_owner_created
    ON runtime_execution_records (owner_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_runtime_execution_records_capability
    ON runtime_execution_records (owner_id, capability_kind, capability_key, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_runtime_execution_records_run
    ON runtime_execution_records (owner_id, run_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_runtime_execution_records_workflow
    ON runtime_execution_records (owner_id, workflow_id, created_at DESC)
    """,
]


async def ensure_runtime_center_schema(engine: AsyncEngine) -> None:
    """Create the runtime execution center schema if it does not exist."""
    async with engine.begin() as conn:
        for statement in SCHEMA_STATEMENTS:
            await conn.execute(text(statement))


async def load_local_agents_log_records(
    engine: AsyncEngine,
    *,
    owner_id: str = "demo-ecommerce-user",
    log_path: Path = LOCAL_AGENTS_LOG_PATH,
) -> dict[str, int]:
    """Load local agent jump JSONL records once when backend starts.

    The `agents.log` cmd tool writes locally and does not depend on backend
    availability. This loader imports unseen local records by `local_log_id`.
    """
    if not log_path.exists():
        return {"loaded": 0, "skipped": 0, "failed": 0}

    loaded = 0
    skipped = 0
    failed = 0

    async with engine.begin() as conn:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    failed += 1
                    continue
                local_log_id = str(record.get("local_log_id") or "").strip()
                if not local_log_id:
                    failed += 1
                    continue

                existing = (
                    await conn.execute(
                        text(
                            """
                            SELECT id
                            FROM runtime_execution_records
                            WHERE owner_id = :owner_id
                              AND source_key = 'agents.log'
                              AND metadata->>'local_log_id' = :local_log_id
                            LIMIT 1
                            """
                        ),
                        {"owner_id": owner_id, "local_log_id": local_log_id},
                    )
                ).first()
                if existing:
                    skipped += 1
                    continue

                event_type = str(record.get("event_type") or "jump")
                from_agent = str(record.get("from_agent") or "unknown-agent")
                to_agent = str(record.get("to_agent") or "unknown-agent")
                reason = str(record.get("reason") or "agent jump")
                summary = str(record.get("handoff_summary") or reason)
                metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
                metadata = {
                    **metadata,
                    "local_log_id": local_log_id,
                    "publisher": "agents-log",
                    "loaded_from": str(log_path),
                    "event_type": event_type,
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "from_workflow": record.get("from_workflow"),
                    "to_workflow": record.get("to_workflow"),
                    "trigger": record.get("trigger"),
                    "local_created_at": record.get("created_at"),
                }
                created_at = _parse_datetime(record.get("created_at"))
                run_id = str(record.get("run_id") or f"agents-log:{uuid4()}")

                await conn.execute(
                    text(
                        """
                        INSERT INTO runtime_execution_records (
                            owner_id,
                            project_key,
                            workflow_id,
                            run_id,
                            parent_run_id,
                            capability_kind,
                            capability_key,
                            capability_label,
                            source_kind,
                            source_key,
                            phase,
                            status,
                            level,
                            title,
                            summary,
                            detail,
                            input_payload,
                            output_payload,
                            tags,
                            metadata,
                            started_at,
                            finished_at,
                            created_at,
                            updated_at
                        ) VALUES (
                            :owner_id,
                            :project_key,
                            :workflow_id,
                            :run_id,
                            :parent_run_id,
                            'agent',
                            :capability_key,
                            :capability_key,
                            'tool',
                            'agents.log',
                            :phase,
                            'completed',
                            :level,
                            :title,
                            :summary,
                            :detail,
                            CAST(:input_payload AS JSONB),
                            CAST(:output_payload AS JSONB),
                            CAST(:tags AS JSONB),
                            CAST(:metadata AS JSONB),
                            :started_at,
                            :finished_at,
                            COALESCE(CAST(:created_at AS TIMESTAMPTZ), NOW()),
                            NOW()
                        )
                        """
                    ),
                    {
                        "owner_id": owner_id,
                        "project_key": record.get("project_key") or "dyshop",
                        "workflow_id": record.get("to_workflow") or record.get("from_workflow"),
                        "run_id": run_id,
                        "parent_run_id": record.get("parent_run_id"),
                        "capability_key": from_agent,
                        "phase": event_type,
                        "level": record.get("level") or "info",
                        "title": f"{from_agent} -> {to_agent}",
                        "summary": summary,
                        "detail": reason,
                        "input_payload": json.dumps(record, ensure_ascii=False),
                        "output_payload": json.dumps(
                            {"to_agent": to_agent, "to_workflow": record.get("to_workflow")},
                            ensure_ascii=False,
                        ),
                        "tags": json.dumps(["agents-log", event_type, from_agent, to_agent], ensure_ascii=False),
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                        "started_at": created_at,
                        "finished_at": created_at,
                        "created_at": created_at,
                    },
                )
                loaded += 1
            except Exception:
                failed += 1

    return {"loaded": loaded, "skipped": skipped, "failed": failed}


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else {}


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _scan_agent_catalog() -> list[dict[str, Any]]:
    registry = _read_yaml_file(TRAE_ROOT / "registry" / "agent-catalog.yaml")
    registry_agents = {
        item.get("id"): item
        for item in registry.get("agents", [])
        if isinstance(item, dict) and item.get("id")
    }

    items: list[dict[str, Any]] = []
    for file_path in sorted((TRAE_ROOT / "agents").rglob("*.md")):
        if file_path.name == "README.md" or file_path.name.endswith("-rubric.md"):
            continue
        capability_key = file_path.stem
        registry_item = registry_agents.get(capability_key, {})
        items.append(
            {
                "capability_kind": "agent",
                "capability_key": capability_key,
                "display_name": capability_key,
                "status": registry_item.get("status", "discovered"),
                "role_type": registry_item.get("role_type"),
                "workflow_scopes": registry_item.get("workflow_scope", []),
                "layer": registry_item.get("layer"),
                "file_path": _relative_path(file_path),
                "source": "registry+filesystem" if registry_item else "filesystem",
                "metadata": {
                    "primary_inputs": registry_item.get("primary_inputs", []),
                    "primary_outputs": registry_item.get("primary_outputs", []),
                    "default_next": registry_item.get("default_next", []),
                    "replaced_by_skill": registry_item.get("replaced_by_skill"),
                },
            }
        )
    return items


def _scan_skill_catalog() -> list[dict[str, Any]]:
    registry = _read_yaml_file(TRAE_ROOT / "registry" / "skill-catalog.yaml")
    registry_skills = {
        item.get("id"): item
        for item in registry.get("skills", [])
        if isinstance(item, dict) and item.get("id")
    }

    items: list[dict[str, Any]] = []
    for file_path in sorted((TRAE_ROOT / "skills").glob("*/SKILL.md")):
        capability_key = file_path.parent.name
        registry_item = registry_skills.get(capability_key, {})
        items.append(
            {
                "capability_kind": "skill",
                "capability_key": capability_key,
                "display_name": capability_key,
                "status": registry_item.get("status", "discovered"),
                "role_type": registry_item.get("role_type"),
                "workflow_scopes": registry_item.get("workflow_scope", []),
                "layer": "skill",
                "file_path": _relative_path(file_path),
                "source": "registry+filesystem" if registry_item else "filesystem",
                "metadata": {
                    "replaces_agents": registry_item.get("replaces_agents", []),
                },
            }
        )
    return items


def _scan_workflow_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for file_path in sorted((TRAE_ROOT / "workflows").glob("*.yaml")):
        workflow_data = _read_yaml_file(file_path)
        if not workflow_data.get("workflow_id"):
            continue
        nodes = workflow_data.get("nodes", [])
        agents = [
            node.get("agent")
            for node in nodes
            if isinstance(node, dict) and node.get("agent")
        ]
        skills = [
            node.get("skill")
            for node in nodes
            if isinstance(node, dict) and node.get("skill")
        ]
        items.append(
            {
                "capability_kind": "workflow",
                "capability_key": workflow_data["workflow_id"],
                "display_name": workflow_data.get("name", workflow_data["workflow_id"]),
                "status": "active",
                "role_type": "workflow",
                "workflow_scopes": [workflow_data["workflow_id"]],
                "layer": "workflow",
                "file_path": _relative_path(file_path),
                "source": "filesystem",
                "metadata": {
                    "entry_rules": workflow_data.get("entry_rules", []),
                    "workflow_controller": workflow_data.get("workflow_controller"),
                    "node_count": len(nodes) if isinstance(nodes, list) else 0,
                    "agents": agents,
                    "skills": skills,
                    "success_criteria": workflow_data.get("success_criteria", []),
                },
            }
        )
    return items


def load_runtime_capability_catalog() -> list[dict[str, Any]]:
    """Discover all runtime capabilities from `.trae` files."""
    catalog_map: dict[tuple[str, str], dict[str, Any]] = {}
    for item in _scan_workflow_catalog() + _scan_agent_catalog() + _scan_skill_catalog():
        catalog_map[(item["capability_kind"], item["capability_key"])] = item
    return sorted(
        catalog_map.values(),
        key=lambda item: (item["capability_kind"], item["display_name"]),
    )


async def _fetch_capability_stats(
    db: AsyncSession, owner_id: str
) -> dict[tuple[str, str], dict[str, Any]]:
    count_rows = (
        await db.execute(
            text(
                """
                SELECT capability_kind, capability_key, COUNT(*) AS record_count
                FROM runtime_execution_records
                WHERE owner_id = :owner_id
                GROUP BY capability_kind, capability_key
                """
            ),
            {"owner_id": owner_id},
        )
    ).mappings().all()
    latest_rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ON (capability_kind, capability_key)
                    capability_kind,
                    capability_key,
                    status AS last_status,
                    created_at AS last_run_at
                FROM runtime_execution_records
                WHERE owner_id = :owner_id
                ORDER BY capability_kind, capability_key, created_at DESC
                """
            ),
            {"owner_id": owner_id},
        )
    ).mappings().all()

    stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for row in count_rows:
        stats[(row["capability_kind"], row["capability_key"])]["record_count"] = row[
            "record_count"
        ]
    for row in latest_rows:
        stats[(row["capability_kind"], row["capability_key"])].update(
            {
                "last_status": row["last_status"],
                "last_run_at": _serialize_datetime(row["last_run_at"]),
            }
        )
    return stats


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def get_runtime_catalog(
    db: AsyncSession, owner_id: str
) -> list[dict[str, Any]]:
    """Return discovered capabilities enriched with runtime stats."""
    base_items = load_runtime_capability_catalog()
    stats = await _fetch_capability_stats(db, owner_id)
    catalog_map = {
        (item["capability_kind"], item["capability_key"]): {**item}
        for item in base_items
    }

    for key, stat in stats.items():
        if key not in catalog_map:
            capability_kind, capability_key = key
            catalog_map[key] = {
                "capability_kind": capability_kind,
                "capability_key": capability_key,
                "display_name": capability_key,
                "status": "runtime_only",
                "role_type": capability_kind,
                "workflow_scopes": [],
                "layer": "runtime",
                "file_path": None,
                "source": "runtime",
                "metadata": {},
            }
        catalog_map[key].update(stat)

    return sorted(
        catalog_map.values(),
        key=lambda item: (item["capability_kind"], item["display_name"]),
    )


async def get_runtime_logs(
    db: AsyncSession,
    owner_id: str,
    *,
    capability_kind: str | None = None,
    capability_key: str | None = None,
    workflow_id: str | None = None,
    project_key: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Return runtime execution records with optional filters."""
    conditions = ["owner_id = :owner_id"]
    params: dict[str, Any] = {
        "owner_id": owner_id,
        "limit": max(1, min(limit, 200)),
    }

    if capability_kind:
        conditions.append("capability_kind = :capability_kind")
        params["capability_kind"] = capability_kind
    if capability_key:
        conditions.append("capability_key = :capability_key")
        params["capability_key"] = capability_key
    if workflow_id:
        conditions.append("workflow_id = :workflow_id")
        params["workflow_id"] = workflow_id
    if project_key:
        conditions.append("project_key = :project_key")
        params["project_key"] = project_key
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if search:
        conditions.append(
            """
            (
                title ILIKE :search_like
                OR COALESCE(summary, '') ILIKE :search_like
                OR COALESCE(detail, '') ILIKE :search_like
                OR COALESCE(workflow_id, '') ILIKE :search_like
                OR capability_key ILIKE :search_like
            )
            """
        )
        params["search_like"] = f"%{search}%"

    query = text(
        f"""
        SELECT
            id,
            owner_id,
            project_key,
            workflow_id,
            run_id,
            parent_run_id,
            capability_kind,
            capability_key,
            capability_label,
            source_kind,
            source_key,
            phase,
            status,
            level,
            title,
            summary,
            detail,
            host_issue,
            review_scorecard,
            input_payload,
            output_payload,
            artifacts,
            tags,
            metadata,
            loop_round,
            started_at,
            finished_at,
            created_at,
            updated_at
        FROM runtime_execution_records
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    rows = (await db.execute(query, params)).mappings().all()
    return [_serialize_runtime_record(row) for row in rows]


def _serialize_runtime_record(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "owner_id": row["owner_id"],
        "project_key": row["project_key"],
        "workflow_id": row["workflow_id"],
        "run_id": row["run_id"],
        "parent_run_id": row["parent_run_id"],
        "capability_kind": row["capability_kind"],
        "capability_key": row["capability_key"],
        "capability_label": row["capability_label"],
        "source_kind": row["source_kind"],
        "source_key": row["source_key"],
        "phase": row["phase"],
        "status": row["status"],
        "level": row["level"],
        "title": row["title"],
        "summary": row["summary"],
        "detail": row["detail"],
        "host_issue": row["host_issue"],
        "review_scorecard": row["review_scorecard"] or {},
        "input_payload": row["input_payload"] or {},
        "output_payload": row["output_payload"] or {},
        "artifacts": row["artifacts"] or [],
        "tags": row["tags"] or [],
        "metadata": row["metadata"] or {},
        "loop_round": row["loop_round"],
        "started_at": _serialize_datetime(row["started_at"]),
        "finished_at": _serialize_datetime(row["finished_at"]),
        "created_at": _serialize_datetime(row["created_at"]),
        "updated_at": _serialize_datetime(row["updated_at"]),
    }


async def create_runtime_record(
    db: AsyncSession,
    owner_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Insert one runtime execution record and return its key fields."""
    def _jsonb_param(value: Any, default: Any) -> str:
        return json.dumps(value if value is not None else default, ensure_ascii=False)

    query = text(
        """
        INSERT INTO runtime_execution_records (
            owner_id,
            project_key,
            workflow_id,
            run_id,
            parent_run_id,
            capability_kind,
            capability_key,
            capability_label,
            source_kind,
            source_key,
            phase,
            status,
            level,
            title,
            summary,
            detail,
            host_issue,
            review_scorecard,
            input_payload,
            output_payload,
            artifacts,
            tags,
            metadata,
            loop_round,
            started_at,
            finished_at,
            updated_at
        ) VALUES (
            :owner_id,
            :project_key,
            :workflow_id,
            :run_id,
            :parent_run_id,
            :capability_kind,
            :capability_key,
            :capability_label,
            :source_kind,
            :source_key,
            :phase,
            :status,
            :level,
            :title,
            :summary,
            :detail,
            :host_issue,
            CAST(:review_scorecard AS JSONB),
            CAST(:input_payload AS JSONB),
            CAST(:output_payload AS JSONB),
            CAST(:artifacts AS JSONB),
            CAST(:tags AS JSONB),
            CAST(:metadata AS JSONB),
            :loop_round,
            :started_at,
            :finished_at,
            NOW()
        )
        RETURNING id, run_id, created_at
        """
    )
    params = {
        "owner_id": owner_id,
        "project_key": payload.get("project_key") or "dyshop",
        "workflow_id": payload.get("workflow_id"),
        "run_id": payload["run_id"],
        "parent_run_id": payload.get("parent_run_id"),
        "capability_kind": payload["capability_kind"],
        "capability_key": payload["capability_key"],
        "capability_label": payload.get("capability_label"),
        "source_kind": payload.get("source_kind"),
        "source_key": payload.get("source_key"),
        "phase": payload.get("phase"),
        "status": payload.get("status") or "running",
        "level": payload.get("level") or "info",
        "title": payload["title"],
        "summary": payload.get("summary"),
        "detail": payload.get("detail"),
        "host_issue": payload.get("host_issue"),
        "review_scorecard": _jsonb_param(payload.get("review_scorecard"), {}),
        "input_payload": _jsonb_param(payload.get("input_payload"), {}),
        "output_payload": _jsonb_param(payload.get("output_payload"), {}),
        "artifacts": _jsonb_param(payload.get("artifacts"), []),
        "tags": _jsonb_param(payload.get("tags"), []),
        "metadata": _jsonb_param(payload.get("metadata"), {}),
        "loop_round": payload.get("loop_round"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
    }
    row = (await db.execute(query, params)).mappings().first()
    return {
        "record_id": str(row["id"]),
        "run_id": row["run_id"],
        "created_at": _serialize_datetime(row["created_at"]),
    }


async def get_runtime_overview(
    db: AsyncSession, owner_id: str, *, log_limit: int = 60
) -> dict[str, Any]:
    """Return summary, catalog and recent logs for the runtime center page."""
    catalog = await get_runtime_catalog(db, owner_id)
    logs = await get_runtime_logs(db, owner_id, limit=log_limit)
    last_24_hours = datetime.now(timezone.utc) - timedelta(hours=24)

    status_rows = (
        await db.execute(
            text(
                """
                SELECT status, COUNT(*) AS total
                FROM runtime_execution_records
                WHERE owner_id = :owner_id
                GROUP BY status
                """
            ),
            {"owner_id": owner_id},
        )
    ).mappings().all()
    kind_rows = (
        await db.execute(
            text(
                """
                SELECT capability_kind, COUNT(*) AS total
                FROM runtime_execution_records
                WHERE owner_id = :owner_id
                GROUP BY capability_kind
                """
            ),
            {"owner_id": owner_id},
        )
    ).mappings().all()
    project_rows = (
        await db.execute(
            text(
                """
                SELECT project_key, COUNT(*) AS total
                FROM runtime_execution_records
                WHERE owner_id = :owner_id
                GROUP BY project_key
                """
            ),
            {"owner_id": owner_id},
        )
    ).mappings().all()

    status_counts = {row["status"]: row["total"] for row in status_rows}
    kind_counts = {row["capability_kind"]: row["total"] for row in kind_rows}
    project_counts = {row["project_key"]: row["total"] for row in project_rows}

    total_records = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM runtime_execution_records WHERE owner_id = :owner_id"
            ),
            {"owner_id": owner_id},
        )
    ).scalar_one()
    recent_records = (
        await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM runtime_execution_records
                WHERE owner_id = :owner_id AND created_at >= :last_24_hours
                """
            ),
            {"owner_id": owner_id, "last_24_hours": last_24_hours},
        )
    ).scalar_one()

    project_keys = sorted(project_counts.keys())
    workflow_ids = sorted(
        {
            item["capability_key"]
            for item in catalog
            if item["capability_kind"] == "workflow"
        }
    )

    return {
        "summary": {
            "total_capabilities": len(catalog),
            "registered_agents": sum(
                1 for item in catalog if item["capability_kind"] == "agent"
            ),
            "registered_workflows": sum(
                1 for item in catalog if item["capability_kind"] == "workflow"
            ),
            "registered_skills": sum(
                1 for item in catalog if item["capability_kind"] == "skill"
            ),
            "total_records": total_records,
            "recent_records_24h": recent_records,
            "status_counts": dict(status_counts),
            "kind_counts": dict(kind_counts),
            "project_counts": dict(project_counts),
        },
        "catalog": catalog,
        "recent_records": logs,
        "filter_options": {
            "project_keys": project_keys,
            "workflow_ids": workflow_ids,
            "status_values": sorted(status_counts.keys()),
            "capability_kinds": ["workflow", "agent", "skill"],
        },
    }
