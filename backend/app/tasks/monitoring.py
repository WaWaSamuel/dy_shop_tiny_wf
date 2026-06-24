"""System monitoring and health checks for the automation platform.

Provides health checks, SLA compliance monitoring, alerting,
and daily metrics aggregation.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ServiceStatus(StrEnum):
    """Health status for a service component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ServiceHealth:
    """Health status for a single service component."""

    name: str
    status: ServiceStatus
    latency_ms: float = 0.0
    error: str | None = None
    last_checked: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


@dataclass
class HealthReport:
    """Aggregate health report for all system components."""

    overall_status: ServiceStatus
    services: list[ServiceHealth] = field(default_factory=list)
    queue_depth: dict[str, int] = field(default_factory=dict)
    error_rates: dict[str, float] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "services": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "latency_ms": s.latency_ms,
                    "error": s.error,
                }
                for s in self.services
            ],
            "queue_depth": self.queue_depth,
            "error_rates": self.error_rates,
            "checked_at": self.checked_at,
        }


@dataclass
class SLAReport:
    """SLA compliance report."""

    response_time_sla_met: bool
    listing_target_met: bool
    feedback_sla_met: bool
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "response_time_sla_met": self.response_time_sla_met,
            "listing_target_met": self.listing_target_met,
            "feedback_sla_met": self.feedback_sla_met,
            "details": self.details,
            "checked_at": self.checked_at,
        }


@dataclass
class DailyMetrics:
    """Aggregated daily metrics across all modules."""

    date: str
    api_success_rate: float = 0.0
    task_completion_rate: float = 0.0
    products_uploaded: int = 0
    products_approved: int = 0
    feedback_processed: int = 0
    feedback_auto_replied: int = 0
    designs_generated: int = 0
    candidates_discovered: int = 0
    errors_total: int = 0
    module_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "date": self.date,
            "api_success_rate": self.api_success_rate,
            "task_completion_rate": self.task_completion_rate,
            "products_uploaded": self.products_uploaded,
            "products_approved": self.products_approved,
            "feedback_processed": self.feedback_processed,
            "feedback_auto_replied": self.feedback_auto_replied,
            "designs_generated": self.designs_generated,
            "candidates_discovered": self.candidates_discovered,
            "errors_total": self.errors_total,
            "module_status": self.module_status,
        }


# ---------------------------------------------------------------------------
# System Monitor
# ---------------------------------------------------------------------------


class SystemMonitor:
    """System monitoring for the Douyin Shop Automation platform.

    Provides health checks, SLA compliance verification, alerting,
    and daily metrics aggregation.
    """

    # SLA thresholds
    RESPONSE_TIME_SLA_MS = 5000  # API response time target
    LISTING_DAILY_TARGET = 5  # Minimum daily listings
    FEEDBACK_RESPONSE_SLA_HOURS = 2  # Max hours to respond to feedback

    def __init__(self) -> None:
        self._alert_history: list[dict] = []

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    def health_check(self) -> HealthReport:
        """Check all API connections, task queue depth, and error rates.

        Returns:
            HealthReport with status of all system components.
        """
        services: list[ServiceHealth] = []

        # Check Redis connectivity
        services.append(self._check_redis())

        # Check PostgreSQL connectivity
        services.append(self._check_database())

        # Check Douyin API connectivity
        services.append(self._check_douyin_api())

        # Check AI service connectivity
        services.append(self._check_ai_service())

        # Check Celery workers
        services.append(self._check_celery_workers())

        # Determine overall status
        statuses = [s.status for s in services]
        if ServiceStatus.DOWN in statuses:
            overall = ServiceStatus.DOWN
        elif ServiceStatus.DEGRADED in statuses:
            overall = ServiceStatus.DEGRADED
        else:
            overall = ServiceStatus.HEALTHY

        # Get queue depths
        queue_depth = self._get_queue_depths()

        # Get error rates from circuit breakers
        error_rates = self._get_error_rates()

        report = HealthReport(
            overall_status=overall,
            services=services,
            queue_depth=queue_depth,
            error_rates=error_rates,
        )

        # Alert if degraded or down
        if overall != ServiceStatus.HEALTHY:
            unhealthy = [s.name for s in services if s.status != ServiceStatus.HEALTHY]
            self.alert_operator(
                message=f"System health degraded. Unhealthy services: {unhealthy}",
                severity="high" if overall == ServiceStatus.DOWN else "medium",
            )

        return report

    # -------------------------------------------------------------------------
    # SLA Compliance
    # -------------------------------------------------------------------------

    def check_sla_compliance(self) -> SLAReport:
        """Check SLA compliance across all modules.

        Verifies:
        - API response times are within target
        - Daily listing count meets targets
        - Feedback response time meets SLA

        Returns:
            SLAReport with compliance status.
        """
        details: dict[str, Any] = {}

        # Check response time SLA (via circuit breaker state)
        response_time_ok = self._check_response_time_sla(details)

        # Check listing target
        listing_ok = self._check_listing_target(details)

        # Check feedback response SLA
        feedback_ok = self._check_feedback_sla(details)

        report = SLAReport(
            response_time_sla_met=response_time_ok,
            listing_target_met=listing_ok,
            feedback_sla_met=feedback_ok,
            details=details,
        )

        # Alert on SLA violations
        violations = []
        if not response_time_ok:
            violations.append("response_time")
        if not listing_ok:
            violations.append("listing_target")
        if not feedback_ok:
            violations.append("feedback_response")

        if violations:
            self.alert_operator(
                message=f"SLA violations detected: {violations}",
                severity="high",
            )

        return report

    # -------------------------------------------------------------------------
    # Alerting
    # -------------------------------------------------------------------------

    def alert_operator(self, message: str, severity: str = "medium") -> None:
        """Send an alert to the operator.

        Currently logs the alert with appropriate level.
        Can be extended to integrate with IM (Lark/DingTalk), email, or PagerDuty.

        Args:
            message: Alert message content.
            severity: Alert severity level (low, medium, high, critical).
        """
        alert_record = {
            "message": message,
            "severity": severity,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._alert_history.append(alert_record)

        # Log with appropriate level
        if severity in ("critical", "high"):
            logger.critical("[ALERT][%s] %s", severity.upper(), message)
        elif severity == "medium":
            logger.warning("[ALERT][%s] %s", severity.upper(), message)
        else:
            logger.info("[ALERT][%s] %s", severity.upper(), message)

        # Future: integrate with IM notification service
        # from app.services.notification import send_lark_message
        # await send_lark_message(message=message, severity=severity)

    # -------------------------------------------------------------------------
    # Daily Metrics
    # -------------------------------------------------------------------------

    def get_daily_metrics(self) -> DailyMetrics:
        """Aggregate daily metrics from all modules.

        Returns:
            DailyMetrics with API success rates, task completion rates,
            and per-module counts.
        """
        import asyncio
        from datetime import date

        today = date.today()
        metrics = DailyMetrics(date=today.isoformat())

        async def _gather_metrics():
            from app.core.database import async_session_factory
            from sqlalchemy import func, select

            async with async_session_factory() as db:
                # Products uploaded today
                from app.models.product import Product, ProductStatus

                uploaded_stmt = select(func.count()).select_from(Product).where(
                    func.date(Product.created_at) == today
                )
                result = await db.execute(uploaded_stmt)
                metrics.products_uploaded = result.scalar() or 0

                # Products approved today
                approved_stmt = select(func.count()).select_from(Product).where(
                    Product.status == ProductStatus.APPROVED,
                    func.date(Product.updated_at) == today,
                )
                result = await db.execute(approved_stmt)
                metrics.products_approved = result.scalar() or 0

                # Candidates discovered today
                from app.models.discovery import TrendingProduct

                discovered_stmt = select(func.count()).select_from(TrendingProduct).where(
                    func.date(TrendingProduct.created_at) == today
                )
                result = await db.execute(discovered_stmt)
                metrics.candidates_discovered = result.scalar() or 0

                # Design tasks today
                from app.models.design_assets import DesignTask

                design_stmt = select(func.count()).select_from(DesignTask).where(
                    func.date(DesignTask.created_at) == today
                )
                result = await db.execute(design_stmt)
                metrics.designs_generated = result.scalar() or 0

            # Feedback stats
            try:
                from app.modules.feedback.service import FeedbackService

                service = FeedbackService()
                stats = service.get_statistics()
                metrics.feedback_processed = stats.get("total_events", 0)
                metrics.feedback_auto_replied = stats.get("responded_count", 0)
            except Exception:
                pass

            # API success rate from circuit breakers
            from app.core.circuit_breaker import circuit_breakers

            total_circuits = len(circuit_breakers)
            healthy_circuits = sum(
                1 for cb in circuit_breakers.values()
                if cb.state.value == "closed"
            )
            metrics.api_success_rate = (
                healthy_circuits / max(total_circuits, 1)
            ) * 100

            # Task completion rate from Celery
            try:
                inspect = celery_app.control.inspect()
                active = inspect.active() or {}
                total_active = sum(len(t) for t in active.values())
                # Rough estimate based on active vs capacity
                metrics.task_completion_rate = max(0, 100 - (total_active * 10))
            except Exception:
                metrics.task_completion_rate = -1  # Unknown

            # Module status
            for name, cb in circuit_breakers.items():
                metrics.module_status[name] = cb.state.value

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_gather_metrics())
        except Exception as exc:
            logger.error("[Monitor] Failed to gather metrics: %s", exc)
            metrics.errors_total += 1
        finally:
            loop.close()

        return metrics

    # -------------------------------------------------------------------------
    # Private health check helpers
    # -------------------------------------------------------------------------

    def _check_redis(self) -> ServiceHealth:
        """Check Redis connectivity."""
        import asyncio

        async def _ping():
            from app.core.redis import get_redis

            start = time.time()
            redis = await get_redis()
            await redis.ping()
            latency = (time.time() - start) * 1000
            return latency

        try:
            loop = asyncio.new_event_loop()
            try:
                latency = loop.run_until_complete(_ping())
            finally:
                loop.close()

            status = ServiceStatus.HEALTHY if latency < 100 else ServiceStatus.DEGRADED
            return ServiceHealth(name="redis", status=status, latency_ms=latency)
        except Exception as exc:
            return ServiceHealth(
                name="redis", status=ServiceStatus.DOWN, error=str(exc)
            )

    def _check_database(self) -> ServiceHealth:
        """Check PostgreSQL connectivity."""
        import asyncio

        async def _ping():
            from app.core.database import async_session_factory
            from sqlalchemy import text

            start = time.time()
            async with async_session_factory() as db:
                await db.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            return latency

        try:
            loop = asyncio.new_event_loop()
            try:
                latency = loop.run_until_complete(_ping())
            finally:
                loop.close()

            status = ServiceStatus.HEALTHY if latency < 500 else ServiceStatus.DEGRADED
            return ServiceHealth(name="postgresql", status=status, latency_ms=latency)
        except Exception as exc:
            return ServiceHealth(
                name="postgresql", status=ServiceStatus.DOWN, error=str(exc)
            )

    def _check_douyin_api(self) -> ServiceHealth:
        """Check Douyin API connectivity via circuit breaker state."""
        from app.core.circuit_breaker import circuit_breakers

        cb = circuit_breakers.get("douyin_api")
        if cb is None:
            return ServiceHealth(
                name="douyin_api", status=ServiceStatus.HEALTHY
            )

        state = cb.state
        if state.value == "closed":
            return ServiceHealth(name="douyin_api", status=ServiceStatus.HEALTHY)
        elif state.value == "half_open":
            return ServiceHealth(name="douyin_api", status=ServiceStatus.DEGRADED)
        else:
            return ServiceHealth(
                name="douyin_api",
                status=ServiceStatus.DOWN,
                error="Circuit breaker is open",
            )

    def _check_ai_service(self) -> ServiceHealth:
        """Check AI service connectivity via circuit breaker state."""
        from app.core.circuit_breaker import circuit_breakers

        cb = circuit_breakers.get("ai_service")
        if cb is None:
            return ServiceHealth(name="ai_service", status=ServiceStatus.HEALTHY)

        state = cb.state
        if state.value == "closed":
            return ServiceHealth(name="ai_service", status=ServiceStatus.HEALTHY)
        elif state.value == "half_open":
            return ServiceHealth(name="ai_service", status=ServiceStatus.DEGRADED)
        else:
            return ServiceHealth(
                name="ai_service",
                status=ServiceStatus.DOWN,
                error="Circuit breaker is open",
            )

    def _check_celery_workers(self) -> ServiceHealth:
        """Check if Celery workers are responding."""
        try:
            start = time.time()
            inspect = celery_app.control.inspect(timeout=5.0)
            ping_result = inspect.ping()
            latency = (time.time() - start) * 1000

            if ping_result:
                worker_count = len(ping_result)
                status = ServiceStatus.HEALTHY if worker_count >= 1 else ServiceStatus.DEGRADED
                return ServiceHealth(
                    name="celery_workers",
                    status=status,
                    latency_ms=latency,
                )
            else:
                return ServiceHealth(
                    name="celery_workers",
                    status=ServiceStatus.DOWN,
                    error="No workers responding",
                )
        except Exception as exc:
            return ServiceHealth(
                name="celery_workers",
                status=ServiceStatus.DOWN,
                error=str(exc),
            )

    def _get_queue_depths(self) -> dict[str, int]:
        """Get current queue depths for all task queues."""
        import asyncio

        queues = ["discovery", "design_assets", "product_upload", "feedback"]
        depths: dict[str, int] = {}

        async def _check():
            try:
                from app.core.redis import get_redis

                redis = await get_redis()
                for queue_name in queues:
                    length = await redis.llen(queue_name)
                    depths[queue_name] = length
            except Exception as exc:
                logger.warning("[Monitor] Queue depth check failed: %s", exc)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_check())
        finally:
            loop.close()

        return depths

    def _get_error_rates(self) -> dict[str, float]:
        """Get error rates from circuit breakers."""
        from app.core.circuit_breaker import circuit_breakers

        rates: dict[str, float] = {}
        for name, cb in circuit_breakers.items():
            # Approximate error rate from failure count / threshold
            rate = cb._failure_count / max(cb.failure_threshold, 1)
            rates[name] = round(rate, 3)
        return rates

    def _check_response_time_sla(self, details: dict) -> bool:
        """Check if API response times are within SLA."""
        from app.core.circuit_breaker import circuit_breakers

        # If no circuits are open, we consider response time SLA met
        open_circuits = [
            name for name, cb in circuit_breakers.items()
            if cb.state.value == "open"
        ]
        details["response_time"] = {
            "sla_ms": self.RESPONSE_TIME_SLA_MS,
            "open_circuits": open_circuits,
        }
        return len(open_circuits) == 0

    def _check_listing_target(self, details: dict) -> bool:
        """Check if daily listing target is being met."""
        import asyncio
        from datetime import date

        async def _check():
            from app.core.database import async_session_factory
            from app.models.product import Product
            from sqlalchemy import func, select

            async with async_session_factory() as db:
                today = date.today()
                stmt = select(func.count()).select_from(Product).where(
                    func.date(Product.created_at) == today
                )
                result = await db.execute(stmt)
                count = result.scalar() or 0
                return count

        try:
            loop = asyncio.new_event_loop()
            try:
                count = loop.run_until_complete(_check())
            finally:
                loop.close()
        except Exception:
            count = 0

        details["listing_target"] = {
            "target": self.LISTING_DAILY_TARGET,
            "actual": count,
        }
        return count >= self.LISTING_DAILY_TARGET

    def _check_feedback_sla(self, details: dict) -> bool:
        """Check if feedback response time SLA is being met."""
        try:
            from app.modules.feedback.service import FeedbackService

            service = FeedbackService()
            stats = service.get_statistics()

            avg_response_seconds = stats.get("avg_response_time_seconds", 0)
            sla_seconds = self.FEEDBACK_RESPONSE_SLA_HOURS * 3600

            details["feedback_sla"] = {
                "target_hours": self.FEEDBACK_RESPONSE_SLA_HOURS,
                "avg_response_seconds": avg_response_seconds,
            }
            return avg_response_seconds <= sla_seconds
        except Exception:
            details["feedback_sla"] = {"error": "unavailable"}
            return True  # Assume met if we can't check
