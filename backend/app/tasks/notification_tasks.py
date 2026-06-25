"""Notification push tasks."""

from __future__ import annotations

import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine in a sync Celery context."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.notification_tasks.send_notification",
    bind=True,
    max_retries=3,
    soft_time_limit=30,
)
def send_notification(
    self: Any,
    channel: str,
    recipient_id: str,
    title: str,
    body: str,
    *,
    template_id: str | None = None,
    template_data: dict[str, Any] | None = None,
    priority: str = "normal",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a single notification.

    Args:
        channel: Notification channel (wechat_work, wechat_mp, email, sms, in_app).
        recipient_id: Recipient identifier.
        title: Notification title.
        body: Notification body.
        template_id: Optional template ID for template messages.
        template_data: Template variable values.
        priority: Message priority (low, normal, high, urgent).
        extra: Additional data (action URLs, etc.).

    Returns:
        Send result with status.
    """
    logger.info(
        f"Sending notification: channel={channel}, "
        f"recipient={recipient_id}, title='{title}'"
    )

    async def _execute() -> dict[str, Any]:
        from app.services.notification import (
            NotificationService,
            NotificationMessage,
            NotificationChannel,
            NotificationPriority,
            WeChatWorkConfig,
        )

        # TODO: Load config from settings/environment
        config = WeChatWorkConfig()
        service = NotificationService(wechat_config=config)

        try:
            message = NotificationMessage(
                title=title,
                body=body,
                channel=NotificationChannel(channel),
                priority=NotificationPriority(priority),
                recipient_id=recipient_id,
                template_id=template_id,
                template_data=template_data or {},
                extra=extra or {},
            )

            result = await service.send(message)

            return {
                "success": result.success,
                "message_id": result.message_id,
                "channel": result.channel.value if result.channel else None,
                "error": result.error,
            }
        finally:
            await service.close()

    try:
        result = _run_async(_execute())
        if not result["success"]:
            logger.warning(
                f"Notification send failed: {result.get('error')}"
            )
        return result
    except Exception as exc:
        logger.error(f"Notification task failed: {exc}")
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))


@celery_app.task(
    name="app.tasks.notification_tasks.send_batch_notifications",
    bind=True,
    max_retries=2,
    soft_time_limit=120,
)
def send_batch_notifications(
    self: Any,
    notifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Send multiple notifications in batch.

    Args:
        notifications: List of notification payloads (same format as send_notification args).

    Returns:
        Batch result with success/failure counts.
    """
    logger.info(f"Sending batch notifications: {len(notifications)} messages")

    async def _execute() -> dict[str, Any]:
        from app.services.notification import (
            NotificationService,
            NotificationMessage,
            NotificationChannel,
            NotificationPriority,
            WeChatWorkConfig,
        )

        config = WeChatWorkConfig()
        service = NotificationService(wechat_config=config)

        try:
            messages = [
                NotificationMessage(
                    title=n["title"],
                    body=n["body"],
                    channel=NotificationChannel(n.get("channel", "wechat_work")),
                    priority=NotificationPriority(n.get("priority", "normal")),
                    recipient_id=n.get("recipient_id", ""),
                    template_id=n.get("template_id"),
                    template_data=n.get("template_data", {}),
                    extra=n.get("extra", {}),
                )
                for n in notifications
            ]

            results = await service.send_batch(messages)

            success_count = sum(1 for r in results if r.success)
            failure_count = len(results) - success_count

            return {
                "total": len(notifications),
                "success": success_count,
                "failed": failure_count,
                "errors": [
                    {"index": i, "error": r.error}
                    for i, r in enumerate(results)
                    if not r.success
                ],
            }
        finally:
            await service.close()

    try:
        result = _run_async(_execute())
        logger.info(
            f"Batch notifications completed: "
            f"{result['success']}/{result['total']} sent"
        )
        return result
    except Exception as exc:
        logger.error(f"Batch notification task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="app.tasks.notification_tasks.notify_order_status_change",
    soft_time_limit=30,
)
def notify_order_status_change(
    order_id: str,
    old_status: str,
    new_status: str,
    order_info: dict[str, Any],
) -> dict[str, Any]:
    """Send notification when order status changes.

    Args:
        order_id: Order UUID.
        old_status: Previous order status.
        new_status: New order status.
        order_info: Order details for the notification.

    Returns:
        Notification result.
    """
    logger.info(
        f"Order status notification: {order_id} "
        f"{old_status} -> {new_status}"
    )

    # Build notification content based on status change
    status_messages = {
        "paid": "Your order has been confirmed and is being processed.",
        "shipped": f"Your order has been shipped! Tracking: {order_info.get('tracking_number', 'N/A')}",
        "delivered": "Your order has been delivered. Please confirm receipt.",
        "completed": "Order completed. Thank you for your purchase!",
        "cancelled": f"Your order has been cancelled. Reason: {order_info.get('cancel_reason', 'N/A')}",
        "refunded": "Your refund has been processed.",
    }

    body = status_messages.get(
        new_status,
        f"Your order status has been updated to: {new_status}",
    )

    # Dispatch to send_notification task
    result = send_notification.delay(
        channel="wechat_work",
        recipient_id=order_info.get("user_id", ""),
        title=f"Order Update: #{order_id[:8]}",
        body=body,
        priority="normal" if new_status != "cancelled" else "high",
        extra={
            "order_id": order_id,
            "action_url": f"/orders/{order_id}",
        },
    )

    return {
        "task_id": result.id,
        "order_id": order_id,
        "notification_sent": True,
    }


@celery_app.task(
    name="app.tasks.notification_tasks.notify_pipeline_complete",
    soft_time_limit=30,
)
def notify_pipeline_complete(
    product_id: str,
    pipeline_id: str,
    status: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Notify when creative pipeline completes.

    Args:
        product_id: Product UUID.
        pipeline_id: Pipeline execution ID.
        status: Pipeline final status (completed/failed).
        summary: Pipeline execution summary.

    Returns:
        Notification result.
    """
    logger.info(
        f"Pipeline completion notification: product={product_id}, "
        f"pipeline={pipeline_id}, status={status}"
    )

    if status == "completed":
        title = "Creative Pipeline Completed"
        body = (
            f"Creative assets for product {product_id[:8]} have been generated.\n"
            f"Steps completed: {summary.get('steps_completed', 0)}/{summary.get('total_steps', 0)}"
        )
        priority = "normal"
    else:
        title = "Creative Pipeline Failed"
        body = (
            f"Creative pipeline for product {product_id[:8]} has failed.\n"
            f"Steps failed: {summary.get('steps_failed', 0)}/{summary.get('total_steps', 0)}\n"
            "Please check and retry."
        )
        priority = "high"

    # Dispatch notification
    result = send_notification.delay(
        channel="wechat_work",
        recipient_id=summary.get("user_id", ""),
        title=title,
        body=body,
        priority=priority,
        extra={
            "product_id": product_id,
            "pipeline_id": pipeline_id,
            "action_url": f"/products/{product_id}/creative",
        },
    )

    return {
        "task_id": result.id,
        "notification_sent": True,
    }
