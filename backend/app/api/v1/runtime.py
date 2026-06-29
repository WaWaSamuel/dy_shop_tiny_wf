"""Runtime execution center APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_ecommerce_user_id, get_db, get_read_db
from app.core.database import write_engine
from app.services.runtime_center import (
    create_runtime_record,
    load_local_agents_log_records,
)
from app.tools.runtime_tools import ToolContext, registry

router = APIRouter()


async def _sync_local_agents_log_queue() -> None:
    """Import local `agents.log` JSONL entries before runtime reads.

    `agents.log` is intentionally able to write while the backend is down or
    already running. Startup import alone means new local handoff logs are
    invisible until a backend restart, so read endpoints sync the queue first.
    """
    await load_local_agents_log_records(write_engine)


class RuntimeRecordWrite(BaseModel):
    """Generic runtime record write payload."""

    project_key: str = "dyshop"
    workflow_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    capability_kind: Literal["agent", "workflow", "skill", "other"] = "workflow"
    capability_key: str = Field(..., min_length=1, max_length=200)
    capability_label: Optional[str] = Field(default=None, max_length=200)
    source_kind: Optional[str] = Field(default=None, max_length=50)
    source_key: Optional[str] = Field(default=None, max_length=200)
    phase: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="running", max_length=50)
    level: str = Field(default="info", max_length=20)
    title: str = Field(..., min_length=1, max_length=300)
    summary: Optional[str] = None
    detail: Optional[str] = None
    host_issue: Optional[str] = None
    review_scorecard: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    loop_round: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WorkflowLogWrite(BaseModel):
    """Compatibility payload for `workflow-log-publish`."""

    project_key: str = "dyshop"
    workflow_id: str = Field(..., min_length=1, max_length=200)
    run_id: Optional[str] = None
    loop_round: Optional[int] = None
    phase: str = Field(..., min_length=1, max_length=100)
    host_issue: Optional[str] = None
    summary: str = Field(..., min_length=1)
    review_scorecard: dict[str, Any] = Field(default_factory=dict)
    decision: Optional[str] = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


def _derive_workflow_log_status(payload: WorkflowLogWrite) -> str:
    if payload.phase == "final":
        return "completed"
    passed = payload.review_scorecard.get("passed")
    if passed is True:
        return "completed"
    if passed is False:
        return "failed"
    if payload.phase == "intake":
        return "running"
    return "running"


@router.get("/overview")
async def runtime_overview(
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Return summary, capability catalog and recent records."""
    await _sync_local_agents_log_queue()
    return await registry.invoke(
        "runtime.get_overview",
        context=ToolContext(user_id=user_id, db=db),
        args={},
    )


@router.get("/catalog")
async def runtime_catalog(
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Return discovered capability catalog with runtime stats."""
    await _sync_local_agents_log_queue()
    return await registry.invoke(
        "runtime.list_capabilities",
        context=ToolContext(user_id=user_id, db=db),
        args={},
    )


@router.get("/logs")
async def list_runtime_logs(
    capability_kind: Optional[str] = None,
    capability_key: Optional[str] = None,
    workflow_id: Optional[str] = None,
    project_key: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = None,
    limit: int = Query(default=80, ge=1, le=200),
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Return runtime records with filters."""
    await _sync_local_agents_log_queue()
    return await registry.invoke(
        "runtime.list_logs",
        context=ToolContext(user_id=user_id, db=db),
        args={
            "capability_kind": capability_kind,
            "capability_key": capability_key,
            "workflow_id": workflow_id,
            "project_key": project_key,
            "status": status_filter,
            "search": search,
            "limit": limit,
        },
    )


@router.post("/executions", status_code=status.HTTP_201_CREATED)
async def create_execution_record(
    payload: RuntimeRecordWrite,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Write a generic runtime execution record."""
    record_payload = payload.model_dump()
    record_payload["run_id"] = record_payload.get("run_id") or str(uuid4())
    return await create_runtime_record(db, user_id, record_payload)


@router.post("/logs", status_code=status.HTTP_201_CREATED)
async def create_workflow_log(
    payload: WorkflowLogWrite,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Compatibility endpoint for `workflow-log-publish`."""
    run_id = payload.run_id or f"{payload.workflow_id}:{uuid4()}"
    created_at = payload.created_at or datetime.utcnow()
    record_payload = {
        "project_key": payload.project_key,
        "workflow_id": payload.workflow_id,
        "run_id": run_id,
        "capability_kind": "workflow",
        "capability_key": payload.workflow_id,
        "capability_label": payload.workflow_id,
        "source_kind": "skill",
        "source_key": "workflow-log-publish",
        "phase": payload.phase,
        "status": _derive_workflow_log_status(payload),
        "level": "info",
        "title": f"{payload.workflow_id} · {payload.phase}",
        "summary": payload.summary,
        "detail": payload.decision,
        "host_issue": payload.host_issue,
        "review_scorecard": payload.review_scorecard,
        "artifacts": payload.artifacts,
        "metadata": {
            **payload.metadata,
            "decision": payload.decision,
            "publisher": "workflow-log-publish",
        },
        "loop_round": payload.loop_round,
        "started_at": created_at,
        "finished_at": created_at if payload.phase == "final" else None,
    }
    return await create_runtime_record(db, user_id, record_payload)
