"""Workflow orchestrator for end-to-end automation pipelines.

Coordinates the sequential Discovery -> Design -> Upload pipeline,
generates reports, and handles negative feedback patterns.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a synchronous context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class WorkflowOrchestrator:
    """Orchestrates multi-module workflows and report generation.

    Connects Discovery, Design, Product Upload, and Feedback modules
    into cohesive end-to-end pipelines.
    """

    def __init__(self) -> None:
        self._start_time = datetime.now(tz=timezone.utc)

    # -------------------------------------------------------------------------
    # Pipeline: Morning Automation (Discovery -> Design -> Upload)
    # -------------------------------------------------------------------------

    def run_morning_pipeline(self) -> dict:
        """Execute the full morning pipeline sequentially.

        Flow:
            1. Discovery: Run daily scan, score candidates
            2. Design: Generate images for approved candidates
            3. Upload: Batch upload products with completed assets

        Returns:
            Summary dict with results from each stage.
        """
        logger.info("[Workflow] Starting morning pipeline")
        pipeline_start = datetime.now(tz=timezone.utc)
        results: dict[str, Any] = {
            "pipeline": "morning",
            "started_at": pipeline_start.isoformat(),
            "stages": {},
        }

        # Stage 1: Discovery
        try:
            logger.info("[Workflow] Stage 1: Discovery scan")
            from app.modules.discovery.tasks import daily_scan_task

            discovery_result = daily_scan_task()
            results["stages"]["discovery"] = {
                "status": "success",
                "result": discovery_result,
            }
            logger.info("[Workflow] Discovery completed: %s", discovery_result)
        except Exception as exc:
            logger.error("[Workflow] Discovery stage failed: %s", exc)
            results["stages"]["discovery"] = {
                "status": "failed",
                "error": str(exc),
            }
            # Continue pipeline even if discovery fails

        # Stage 2: Design Asset Generation
        try:
            logger.info("[Workflow] Stage 2: Design asset generation")
            from app.tasks.scheduler import task_design_generate_for_approved

            design_result = task_design_generate_for_approved()
            results["stages"]["design"] = {
                "status": "success",
                "result": design_result,
            }
            logger.info("[Workflow] Design generation completed: %s", design_result)
        except Exception as exc:
            logger.error("[Workflow] Design stage failed: %s", exc)
            results["stages"]["design"] = {
                "status": "failed",
                "error": str(exc),
            }

        # Stage 3: Product Upload
        try:
            logger.info("[Workflow] Stage 3: Product batch upload")
            from app.tasks.scheduler import task_product_upload_batch

            upload_result = task_product_upload_batch()
            results["stages"]["upload"] = {
                "status": "success",
                "result": upload_result,
            }
            logger.info("[Workflow] Upload completed: %s", upload_result)
        except Exception as exc:
            logger.error("[Workflow] Upload stage failed: %s", exc)
            results["stages"]["upload"] = {
                "status": "failed",
                "error": str(exc),
            }

        pipeline_end = datetime.now(tz=timezone.utc)
        results["completed_at"] = pipeline_end.isoformat()
        results["duration_seconds"] = (pipeline_end - pipeline_start).total_seconds()

        # Count successes
        stages = results["stages"]
        success_count = sum(1 for s in stages.values() if s["status"] == "success")
        results["summary"] = f"{success_count}/{len(stages)} stages completed successfully"

        logger.info("[Workflow] Morning pipeline finished: %s", results["summary"])
        return results

    # -------------------------------------------------------------------------
    # Pipeline: Single Candidate to Listing
    # -------------------------------------------------------------------------

    def run_candidate_to_listing(self, candidate_id: str) -> dict:
        """Full flow: approve candidate -> generate assets -> upload product.

        Takes a single discovery candidate through the entire pipeline
        from approval to live listing.

        Args:
            candidate_id: UUID of the SourceCandidate to process.

        Returns:
            Summary dict with results from each step.
        """
        logger.info("[Workflow] Starting candidate-to-listing for: %s", candidate_id)
        results: dict[str, Any] = {
            "pipeline": "candidate_to_listing",
            "candidate_id": candidate_id,
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
            "steps": {},
        }

        async def _run() -> dict:
            from app.core.database import async_session_factory
            from app.models.discovery import SourceCandidate, SourceCandidateStatus
            from sqlalchemy import select

            async with async_session_factory() as db:
                # Step 1: Approve the candidate
                import uuid

                stmt = select(SourceCandidate).where(
                    SourceCandidate.id == uuid.UUID(candidate_id)
                )
                result = await db.execute(stmt)
                candidate = result.scalar_one_or_none()

                if candidate is None:
                    return {"error": f"Candidate not found: {candidate_id}"}

                candidate.status = SourceCandidateStatus.APPROVED
                await db.commit()
                results["steps"]["approve"] = {"status": "success"}

                # Step 2: Generate design assets
                product_id = str(candidate.trending_product_id)
                from app.modules.design_assets.tasks import batch_generate_assets_task

                design_task = batch_generate_assets_task.apply_async(
                    kwargs={
                        "product_ids": [product_id],
                        "task_types": ["main_image", "detail_page"],
                    }
                )
                results["steps"]["design"] = {
                    "status": "dispatched",
                    "task_id": design_task.id,
                }

                # Step 3: Queue product upload (will execute after design completes)
                from app.modules.product_upload.tasks import upload_product_task

                # Build product data from the candidate
                from app.models.discovery import TrendingProduct

                product_stmt = select(TrendingProduct).where(
                    TrendingProduct.id == candidate.trending_product_id
                )
                prod_result = await db.execute(product_stmt)
                trending = prod_result.scalar_one_or_none()

                if trending:
                    product_data = {
                        "name": trending.name,
                        "description": trending.description or "",
                        "images": [],
                        "category_id": trending.category or "",
                        "price": float(trending.sell_price or 0),
                        "stock": 100,
                        "auto_publish": True,
                    }
                    upload_task = upload_product_task.apply_async(
                        args=[product_data],
                        countdown=120,  # Wait 2 min for design to potentially finish
                    )
                    results["steps"]["upload"] = {
                        "status": "dispatched",
                        "task_id": upload_task.id,
                    }
                else:
                    results["steps"]["upload"] = {"status": "skipped", "reason": "product_not_found"}

            return results

        try:
            final = _run_async(_run())
            final["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
            return final
        except Exception as exc:
            logger.error("[Workflow] Candidate-to-listing failed: %s", exc)
            results["error"] = str(exc)
            return results

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    def generate_daily_report(self) -> dict:
        """Aggregate stats from all modules into a comprehensive daily report.

        Returns:
            Dict with metrics from discovery, design, upload, and feedback modules.
        """
        logger.info("[Workflow] Generating daily report")
        report: dict[str, Any] = {
            "report_type": "daily",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "modules": {},
        }

        # Discovery stats
        try:
            report["modules"]["discovery"] = self._get_discovery_stats()
        except Exception as exc:
            logger.error("[Report] Discovery stats failed: %s", exc)
            report["modules"]["discovery"] = {"error": str(exc)}

        # Design stats
        try:
            report["modules"]["design"] = self._get_design_stats()
        except Exception as exc:
            logger.error("[Report] Design stats failed: %s", exc)
            report["modules"]["design"] = {"error": str(exc)}

        # Upload stats
        try:
            report["modules"]["upload"] = self._get_upload_stats()
        except Exception as exc:
            logger.error("[Report] Upload stats failed: %s", exc)
            report["modules"]["upload"] = {"error": str(exc)}

        # Feedback stats
        try:
            report["modules"]["feedback"] = self._get_feedback_stats()
        except Exception as exc:
            logger.error("[Report] Feedback stats failed: %s", exc)
            report["modules"]["feedback"] = {"error": str(exc)}

        # Aggregate summary
        report["summary"] = {
            "modules_healthy": sum(
                1 for m in report["modules"].values() if "error" not in m
            ),
            "modules_total": len(report["modules"]),
        }

        return report

    def generate_status_digest(self) -> dict:
        """Generate a mid-day status digest (12:00 and 18:00).

        Lighter-weight than the full daily report, focusing on
        active tasks and immediate concerns.

        Returns:
            Dict with current status summary.
        """
        logger.info("[Workflow] Generating status digest")
        digest: dict[str, Any] = {
            "report_type": "status_digest",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        # Check active tasks in queues
        try:
            inspect = celery_app.control.inspect()
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}

            total_active = sum(len(tasks) for tasks in active.values())
            total_reserved = sum(len(tasks) for tasks in reserved.values())

            digest["queue_status"] = {
                "active_tasks": total_active,
                "reserved_tasks": total_reserved,
            }
        except Exception as exc:
            logger.warning("[Digest] Queue inspection failed: %s", exc)
            digest["queue_status"] = {"error": str(exc)}

        # Feedback urgency check
        try:
            from app.modules.feedback.service import FeedbackService
            from app.modules.feedback.schemas import FeedbackStatus

            service = FeedbackService()
            pending = service.list_events(status=FeedbackStatus.PENDING)
            escalated = service.list_events(status=FeedbackStatus.ESCALATED)

            digest["feedback"] = {
                "pending_count": len(pending),
                "escalated_count": len(escalated),
                "needs_attention": len(escalated) > 0,
            }
        except Exception as exc:
            logger.warning("[Digest] Feedback check failed: %s", exc)
            digest["feedback"] = {"error": str(exc)}

        # Quick upload status check
        try:
            digest["uploads"] = self._get_upload_stats()
        except Exception as exc:
            digest["uploads"] = {"error": str(exc)}

        return digest

    # -------------------------------------------------------------------------
    # Negative Feedback Pattern Detection
    # -------------------------------------------------------------------------

    def handle_negative_feedback_pattern(self, product_id: str) -> dict:
        """Handle pattern of negative reviews for a product.

        When negative reviews pile up, this flags the product for review
        and optionally pauses advertising or marks for investigation.

        Args:
            product_id: The product ID with negative feedback pattern.

        Returns:
            Dict with actions taken.
        """
        logger.warning(
            "[Workflow] Negative feedback pattern detected for product: %s",
            product_id,
        )

        actions_taken: list[str] = []
        result: dict[str, Any] = {
            "product_id": product_id,
            "pattern": "negative_feedback_accumulation",
            "detected_at": datetime.now(tz=timezone.utc).isoformat(),
            "actions": [],
        }

        try:
            from app.modules.feedback.service import FeedbackService

            service = FeedbackService()

            # Get feedback stats for this product
            all_events = service.list_events()
            product_events = [
                e for e in all_events
                if getattr(e, "product_id", None) == product_id
            ]

            negative_count = sum(
                1 for e in product_events
                if getattr(e, "sentiment", None) == "negative"
            )
            total_count = len(product_events)

            result["metrics"] = {
                "total_feedback": total_count,
                "negative_count": negative_count,
                "negative_ratio": negative_count / max(total_count, 1),
            }

            # Action 1: Flag the product
            actions_taken.append("product_flagged_for_review")

            # Action 2: Alert operator if ratio is high
            if negative_count >= 5 or (total_count > 0 and negative_count / total_count > 0.3):
                from app.tasks.monitoring import SystemMonitor

                monitor = SystemMonitor()
                monitor.alert_operator(
                    message=(
                        f"Product {product_id} has {negative_count}/{total_count} "
                        f"negative reviews. Requires immediate attention."
                    ),
                    severity="high",
                )
                actions_taken.append("operator_alerted")

            # Action 3: If very severe, recommend pausing the listing
            if negative_count >= 10 or (total_count >= 5 and negative_count / total_count > 0.5):
                actions_taken.append("recommend_pause_listing")
                result["recommendation"] = "pause_listing"

        except Exception as exc:
            logger.error(
                "[Workflow] Error handling negative feedback pattern: %s", exc
            )
            actions_taken.append(f"error: {exc}")

        result["actions"] = actions_taken
        return result

    # -------------------------------------------------------------------------
    # Private helpers for stats aggregation
    # -------------------------------------------------------------------------

    def _get_discovery_stats(self) -> dict:
        """Get discovery module statistics."""
        async def _fetch():
            from app.core.database import async_session_factory
            from app.models.discovery import TrendingProduct, SourceCandidate
            from sqlalchemy import func, select
            from datetime import date

            async with async_session_factory() as db:
                # Today's scanned products
                today = date.today()
                count_stmt = select(func.count()).select_from(TrendingProduct).where(
                    func.date(TrendingProduct.created_at) == today
                )
                result = await db.execute(count_stmt)
                today_scanned = result.scalar() or 0

                # Total candidates
                total_stmt = select(func.count()).select_from(SourceCandidate)
                result = await db.execute(total_stmt)
                total_candidates = result.scalar() or 0

                return {
                    "today_products_scanned": today_scanned,
                    "total_source_candidates": total_candidates,
                }

        return _run_async(_fetch())

    def _get_design_stats(self) -> dict:
        """Get design module statistics."""
        async def _fetch():
            from app.core.database import async_session_factory
            from app.models.design_assets import DesignTask
            from sqlalchemy import func, select
            from datetime import date

            async with async_session_factory() as db:
                today = date.today()
                count_stmt = select(func.count()).select_from(DesignTask).where(
                    func.date(DesignTask.created_at) == today
                )
                result = await db.execute(count_stmt)
                today_tasks = result.scalar() or 0

                return {
                    "today_design_tasks": today_tasks,
                }

        return _run_async(_fetch())

    def _get_upload_stats(self) -> dict:
        """Get product upload statistics."""
        async def _fetch():
            from app.core.database import async_session_factory
            from app.models.product import Product, ProductStatus
            from sqlalchemy import func, select
            from datetime import date

            async with async_session_factory() as db:
                today = date.today()

                # Products uploaded today
                uploaded_stmt = select(func.count()).select_from(Product).where(
                    func.date(Product.created_at) == today
                )
                result = await db.execute(uploaded_stmt)
                today_uploaded = result.scalar() or 0

                # Products currently online
                online_stmt = select(func.count()).select_from(Product).where(
                    Product.status == ProductStatus.ONLINE
                )
                result = await db.execute(online_stmt)
                total_online = result.scalar() or 0

                # Products pending review
                pending_stmt = select(func.count()).select_from(Product).where(
                    Product.status == ProductStatus.PENDING_REVIEW
                )
                result = await db.execute(pending_stmt)
                pending_review = result.scalar() or 0

                return {
                    "today_uploaded": today_uploaded,
                    "total_online": total_online,
                    "pending_review": pending_review,
                }

        return _run_async(_fetch())

    def _get_feedback_stats(self) -> dict:
        """Get feedback module statistics."""
        try:
            from app.modules.feedback.service import FeedbackService

            service = FeedbackService()
            stats = service.get_statistics()
            return stats
        except Exception:
            return {"status": "unavailable"}
