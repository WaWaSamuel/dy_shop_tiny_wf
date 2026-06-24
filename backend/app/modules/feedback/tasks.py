"""Celery tasks for periodic feedback processing.

Defines scheduled tasks for polling reviews, after-sale tickets,
processing pending events, and nightly batch operations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from celery import shared_task
from celery.schedules import crontab

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code in a sync Celery task context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_feedback_service():
    """Create a FeedbackService instance for task execution."""
    from app.modules.feedback.service import FeedbackService

    return FeedbackService()


@shared_task(
    name="app.tasks.feedback.poll_reviews",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def poll_reviews_task(self) -> dict:
    """Periodic task: Poll 抖店 for new product reviews every 5 minutes.

    Ingests new reviews and queues them for classification/response.
    """
    logger.info("Starting poll_reviews_task")

    try:
        service = _get_feedback_service()

        async def _poll():
            events = await service.ingest_reviews()
            # Queue each event for processing
            for event in events:
                process_feedback_event_task.delay(event.id)
            return len(events)

        count = _run_async(_poll())
        logger.info("poll_reviews_task completed: ingested %d reviews", count)
        return {"status": "success", "ingested_count": count}

    except Exception as exc:
        logger.error("poll_reviews_task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.feedback.poll_after_sale",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def poll_after_sale_task(self) -> dict:
    """Periodic task: Poll 抖店 for after-sale tickets every 3 minutes.

    After-sale disputes have higher urgency and shorter SLA.
    """
    logger.info("Starting poll_after_sale_task")

    try:
        service = _get_feedback_service()

        async def _poll():
            events = await service.ingest_after_sale_tickets()
            for event in events:
                # Higher priority for after-sale events
                process_feedback_event_task.apply_async(
                    args=[event.id],
                    priority=8,
                )
            return len(events)

        count = _run_async(_poll())
        logger.info("poll_after_sale_task completed: ingested %d tickets", count)
        return {"status": "success", "ingested_count": count}

    except Exception as exc:
        logger.error("poll_after_sale_task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.feedback.process_feedback_event",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def process_feedback_event_task(self, event_id: str) -> dict:
    """Process a single feedback event: classify and generate response.

    This is the main processing pipeline task. It runs classification
    (type + sentiment + urgency) and then generates an appropriate
    auto-reply or draft for human review.

    Args:
        event_id: The feedback event ID to process.
    """
    logger.info("Processing feedback event: %s", event_id)

    try:
        service = _get_feedback_service()

        async def _process():
            event = service.get_event(event_id)
            if event is None:
                logger.warning("Event not found: %s", event_id)
                return {"status": "not_found", "event_id": event_id}

            # Step 1: Classify
            event = await service.classify_feedback(event)

            # Step 2: Generate response
            event = await service.generate_response(event)

            # Step 3: Auto-send if safe (low urgency, positive/neutral)
            from app.modules.feedback.schemas import FeedbackStatus

            if event.status == FeedbackStatus.DRAFT_READY and event.urgency_score <= 2:
                await service.submit_reply(
                    event_id=event.id,
                    reply_content=event.auto_reply,
                )
                return {
                    "status": "auto_replied",
                    "event_id": event_id,
                    "urgency": event.urgency_score,
                }

            return {
                "status": event.status.value,
                "event_id": event_id,
                "urgency": event.urgency_score,
                "needs_approval": event.status == FeedbackStatus.AWAITING_APPROVAL,
            }

        result = _run_async(_process())
        logger.info("process_feedback_event_task result: %s", result)
        return result

    except Exception as exc:
        logger.error("process_feedback_event_task failed for %s: %s", event_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.feedback.batch_process_unanswered",
    bind=True,
    max_retries=1,
)
def batch_process_unanswered_task(self) -> dict:
    """Nightly task (22:00): Process any unanswered feedback events.

    Finds all events that are still pending or have drafts ready
    but haven't been replied to, and attempts to process/escalate them.
    """
    logger.info("Starting batch_process_unanswered_task")

    try:
        service = _get_feedback_service()

        async def _batch():
            from app.modules.feedback.schemas import FeedbackStatus

            # Find unprocessed events
            pending_events = service.list_events(status=FeedbackStatus.PENDING)
            draft_events = service.list_events(status=FeedbackStatus.DRAFT_READY)

            processed = 0
            escalated = 0

            # Process pending events
            for event in pending_events:
                event = await service.classify_feedback(event)
                event = await service.generate_response(event)
                processed += 1

            # Auto-send draft replies that are low urgency
            for event in draft_events:
                if event.urgency_score <= 2 and event.auto_reply:
                    await service.submit_reply(
                        event_id=event.id,
                        reply_content=event.auto_reply,
                    )
                    processed += 1
                else:
                    # Escalate high-urgency unanswered events
                    event.status = FeedbackStatus.ESCALATED
                    escalated += 1

            return {
                "processed": processed,
                "escalated": escalated,
                "pending_remaining": len(pending_events) - processed,
            }

        result = _run_async(_batch())
        logger.info("batch_process_unanswered_task completed: %s", result)
        return {"status": "success", **result}

    except Exception as exc:
        logger.error("batch_process_unanswered_task failed: %s", exc)
        raise self.retry(exc=exc)


# --- Celery Beat schedule registration ---
celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "poll-reviews-every-5min": {
        "task": "app.tasks.feedback.poll_reviews",
        "schedule": 300.0,  # 5 minutes
        "options": {"queue": "feedback"},
    },
    "poll-after-sale-every-3min": {
        "task": "app.tasks.feedback.poll_after_sale",
        "schedule": 180.0,  # 3 minutes
        "options": {"queue": "feedback"},
    },
    "batch-process-unanswered-nightly": {
        "task": "app.tasks.feedback.batch_process_unanswered",
        "schedule": crontab(hour=22, minute=0),
        "options": {"queue": "feedback"},
    },
}
