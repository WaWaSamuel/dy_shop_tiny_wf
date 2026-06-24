"""System management API router.

Provides endpoints for health checks, metrics, reports, and manual
pipeline triggers for the Douyin Shop Automation platform.

Endpoints:
- GET /system/health - Health check with detailed service status
- GET /system/metrics - Daily metrics aggregation
- GET /system/report/daily - Full daily report from all modules
- POST /system/scan/trigger - Manual trigger of the morning pipeline
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

system_router = APIRouter(tags=["System"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ServiceHealthResponse(BaseModel):
    """Health status of a single service."""

    name: str
    status: str
    latency_ms: float = 0.0
    error: str | None = None


class HealthResponse(BaseModel):
    """System health check response."""

    overall_status: str
    services: list[ServiceHealthResponse]
    queue_depth: dict[str, int] = Field(default_factory=dict)
    error_rates: dict[str, float] = Field(default_factory=dict)
    checked_at: str


class MetricsResponse(BaseModel):
    """Daily metrics response."""

    date: str
    api_success_rate: float
    task_completion_rate: float
    products_uploaded: int
    products_approved: int
    feedback_processed: int
    feedback_auto_replied: int
    designs_generated: int
    candidates_discovered: int
    errors_total: int
    module_status: dict[str, str] = Field(default_factory=dict)


class DailyReportResponse(BaseModel):
    """Daily report response."""

    report_type: str
    generated_at: str
    modules: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class TriggerResponse(BaseModel):
    """Pipeline trigger response."""

    status: str
    message: str
    triggered_at: str
    pipeline: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@system_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Comprehensive health check of all system components.

    Checks Redis, PostgreSQL, Douyin API, AI service, and Celery workers.
    Returns overall status and individual service statuses.
    """
    from app.tasks.monitoring import SystemMonitor

    monitor = SystemMonitor()
    report = monitor.health_check()

    return HealthResponse(
        overall_status=report.overall_status.value,
        services=[
            ServiceHealthResponse(
                name=s.name,
                status=s.status.value,
                latency_ms=s.latency_ms,
                error=s.error,
            )
            for s in report.services
        ],
        queue_depth=report.queue_depth,
        error_rates=report.error_rates,
        checked_at=report.checked_at,
    )


@system_router.get("/metrics", response_model=MetricsResponse)
async def daily_metrics() -> MetricsResponse:
    """Get aggregated daily metrics from all modules.

    Returns API success rates, task completion rates, and per-module
    counts for the current day.
    """
    from app.tasks.monitoring import SystemMonitor

    monitor = SystemMonitor()
    metrics = monitor.get_daily_metrics()

    return MetricsResponse(
        date=metrics.date,
        api_success_rate=metrics.api_success_rate,
        task_completion_rate=metrics.task_completion_rate,
        products_uploaded=metrics.products_uploaded,
        products_approved=metrics.products_approved,
        feedback_processed=metrics.feedback_processed,
        feedback_auto_replied=metrics.feedback_auto_replied,
        designs_generated=metrics.designs_generated,
        candidates_discovered=metrics.candidates_discovered,
        errors_total=metrics.errors_total,
        module_status=metrics.module_status,
    )


@system_router.get("/report/daily", response_model=DailyReportResponse)
async def daily_report() -> DailyReportResponse:
    """Generate a comprehensive daily report aggregating all module stats.

    Returns a detailed breakdown from discovery, design, upload,
    and feedback modules.
    """
    from app.tasks.workflow import WorkflowOrchestrator

    orchestrator = WorkflowOrchestrator()
    report = orchestrator.generate_daily_report()

    return DailyReportResponse(
        report_type=report.get("report_type", "daily"),
        generated_at=report.get("generated_at", datetime.now(tz=timezone.utc).isoformat()),
        modules=report.get("modules", {}),
        summary=report.get("summary", {}),
    )


@system_router.post("/scan/trigger", response_model=TriggerResponse)
async def trigger_morning_pipeline(background_tasks: BackgroundTasks) -> TriggerResponse:
    """Manually trigger the morning pipeline (Discovery -> Design -> Upload).

    Runs the full sequential pipeline as a background task.
    This is useful for ad-hoc runs outside the scheduled 06:00-08:00 window.

    Returns immediately with acknowledgment; pipeline executes in background.
    """
    logger.info("[System] Manual pipeline trigger received")

    def _run_pipeline():
        """Execute the morning pipeline in background."""
        from app.tasks.workflow import WorkflowOrchestrator

        try:
            orchestrator = WorkflowOrchestrator()
            result = orchestrator.run_morning_pipeline()
            logger.info("[System] Manual pipeline completed: %s", result.get("summary"))
        except Exception as exc:
            logger.error("[System] Manual pipeline failed: %s", exc)

    background_tasks.add_task(_run_pipeline)

    return TriggerResponse(
        status="accepted",
        message="Morning pipeline triggered. Running in background.",
        triggered_at=datetime.now(tz=timezone.utc).isoformat(),
        pipeline="morning",
    )


@system_router.get("/sla")
async def sla_compliance() -> dict:
    """Check SLA compliance across all modules.

    Returns response time SLA, listing targets, and feedback
    response time compliance status.
    """
    from app.tasks.monitoring import SystemMonitor

    monitor = SystemMonitor()
    report = monitor.check_sla_compliance()
    return report.to_dict()


@system_router.get("/status/digest")
async def status_digest() -> dict:
    """Get a lightweight status digest.

    Returns active task counts, pending feedback, and quick
    module health indicators.
    """
    from app.tasks.workflow import WorkflowOrchestrator

    orchestrator = WorkflowOrchestrator()
    return orchestrator.generate_status_digest()
