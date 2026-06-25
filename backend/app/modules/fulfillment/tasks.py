"""Celery tasks for the fulfillment module.

Drives both flows asynchronously:
    Flow 1: source_and_list_task — match 1688 supply, price, list on 抖店.
    Flow 2: process_order_task — ingest a 抖店 order then place the 1688 order,
            track_logistics_task — poll 1688 logistics and sync shipment back,
            poll_new_orders_task — fallback ingestion of new paid 抖店 orders.
"""

import asyncio
import logging
import uuid
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine to completion in a Celery worker context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _build_service():
    """Create a FulfillmentService bound to a fresh DB session + rate limiter."""
    from app.core.database import async_session_factory
    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.modules.fulfillment.service import FulfillmentService

    redis = await get_redis()
    rate_limiter = TokenBucketRateLimiter(redis=redis)
    session = async_session_factory()
    service = FulfillmentService(db=session, rate_limiter=rate_limiter)
    return service, session


@celery_app.task(
    name="app.modules.fulfillment.tasks.source_and_list_task",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue="fulfillment",
)
def source_and_list_task(self, payload: dict[str, Any]) -> dict[str, Any]:
    """Flow 1: find a same-source 1688 supply, price, and list on 抖店.

    Args:
        payload: Serialized SourceListingInput fields (title/category/
            image_url/description/asset_urls/source_candidate_id/auto_publish).

    Returns:
        Summary of the resulting SourcedListing.
    """
    logger.info("[Fulfillment] source_and_list for '%s'", payload.get("title", "")[:40])

    async def _execute() -> dict[str, Any]:
        from app.modules.fulfillment.service import SourceListingInput

        service, session = await _build_service()
        try:
            data = SourceListingInput(
                title=payload["title"],
                category=payload.get("category", ""),
                image_url=payload.get("image_url"),
                description=payload.get("description", ""),
                asset_urls=payload.get("asset_urls", []),
                source_candidate_id=payload.get("source_candidate_id"),
                auto_publish=payload.get("auto_publish", False),
            )
            listing = await service.source_and_list(data)
            await session.commit()

            result = {
                "listing_id": str(listing.id),
                "status": listing.status.value
                if hasattr(listing.status, "value")
                else listing.status,
                "match_score": float(listing.match_score or 0.0),
                "sell_price": float(listing.sell_price or 0.0),
                "achieved_margin": float(listing.achieved_margin or 0.0),
                "douyin_product_id": listing.douyin_product_id,
            }

            # If listed, follow review status until terminal (reuses upload poller).
            if listing.douyin_product_id and listing.product_id:
                from app.modules.product_upload.tasks import check_review_status_task

                check_review_status_task.apply_async(
                    args=[listing.douyin_product_id],
                    kwargs={"internal_product_id": str(listing.product_id)},
                    countdown=300,
                )
            return result
        except Exception:
            await session.rollback()
            raise
        finally:
            await service.close()
            await session.close()

    try:
        return _run_async(_execute())
    except Exception as exc:
        logger.error("[Fulfillment] source_and_list failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.modules.fulfillment.tasks.process_order_task",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue="fulfillment",
)
def process_order_task(self, order_payload: dict[str, Any]) -> dict[str, Any]:
    """Flow 2: ingest a 抖店 order, then place the matching 1688 order.

    Args:
        order_payload: Raw 抖店 order dict (webhook or poll shape).

    Returns:
        Summary of the order + supplier order outcome.
    """
    logger.info(
        "[Fulfillment] process_order for 抖店 order %s",
        order_payload.get("order_id") or order_payload.get("shop_order_id"),
    )

    async def _execute() -> dict[str, Any]:
        from app.models.fulfillment import OrderStatus

        service, session = await _build_service()
        try:
            order = await service.ingest_order(order_payload)
            await session.commit()

            # Only attempt fulfillment when not already sourced/failed.
            supplier_order = None
            if order.status in (OrderStatus.RECEIVED, OrderStatus.SOURCING):
                try:
                    supplier_order = await service.fulfill_order(order)
                    await session.commit()
                except ValueError as e:
                    # No linked 1688 offer — keep the order for manual handling.
                    await session.commit()
                    logger.warning(
                        "[Fulfillment] order %s not auto-fulfillable: %s",
                        order.douyin_order_id,
                        e,
                    )

            result = {
                "order_id": str(order.id),
                "douyin_order_id": order.douyin_order_id,
                "order_status": order.status.value
                if hasattr(order.status, "value")
                else order.status,
                "supplier_order_id": str(supplier_order.id) if supplier_order else None,
                "alibaba_order_id": supplier_order.alibaba_order_id
                if supplier_order
                else None,
            }

            # Kick off logistics tracking when the 1688 order was created.
            if supplier_order and supplier_order.alibaba_order_id:
                track_logistics_task.apply_async(
                    args=[str(supplier_order.id)],
                    countdown=600,
                )
            return result
        except Exception:
            await session.rollback()
            raise
        finally:
            await service.close()
            await session.close()

    try:
        return _run_async(_execute())
    except Exception as exc:
        logger.error("[Fulfillment] process_order failed: %s", exc)
        raise self.retry(exc=exc)


# Poll logistics every 30 min, up to ~7 days, until delivered.
_LOGISTICS_POLL_INTERVAL = 1800
_MAX_LOGISTICS_POLLS = 336


@celery_app.task(
    name="app.modules.fulfillment.tasks.track_logistics_task",
    bind=True,
    max_retries=_MAX_LOGISTICS_POLLS,
    default_retry_delay=_LOGISTICS_POLL_INTERVAL,
    queue="fulfillment",
)
def track_logistics_task(self, supplier_order_id: str) -> dict[str, Any]:
    """Flow 2: poll 1688 logistics for a supplier order until delivered.

    Re-schedules itself every 30 minutes until a terminal (delivered) state
    is reached or the poll budget is exhausted. Pushes the shipment back to
    抖店 on first tracking-number availability (handled in the service).

    Args:
        supplier_order_id: UUID of the SupplierOrder to track.

    Returns:
        Snapshot of the latest logistics status.
    """
    logger.info(
        "[Fulfillment] track_logistics for supplier_order %s (poll %d/%d)",
        supplier_order_id,
        self.request.retries + 1,
        _MAX_LOGISTICS_POLLS,
    )

    async def _execute() -> dict[str, Any]:
        from sqlalchemy import select

        from app.models.fulfillment import SupplierOrder, SupplierOrderStatus

        service, session = await _build_service()
        try:
            res = await session.execute(
                select(SupplierOrder).where(
                    SupplierOrder.id == uuid.UUID(supplier_order_id)
                )
            )
            supplier_order = res.scalar_one_or_none()
            if supplier_order is None:
                return {"supplier_order_id": supplier_order_id, "status": "not_found"}

            track = await service.track_logistics(supplier_order)
            await session.commit()

            terminal = supplier_order.status in (
                SupplierOrderStatus.SUCCESS,
                SupplierOrderStatus.CANCELLED,
                SupplierOrderStatus.FAILED,
            )
            return {
                "supplier_order_id": supplier_order_id,
                "status": supplier_order.status.value
                if hasattr(supplier_order.status, "value")
                else supplier_order.status,
                "tracking_no": supplier_order.tracking_no,
                "logistics_status": track.status if track else None,
                "terminal": terminal,
            }
        except Exception:
            await session.rollback()
            raise
        finally:
            await service.close()
            await session.close()

    try:
        result = _run_async(_execute())
    except Exception as exc:
        logger.error("[Fulfillment] track_logistics failed: %s", exc)
        raise self.retry(exc=exc, countdown=_LOGISTICS_POLL_INTERVAL)

    if result.get("terminal") or result.get("status") == "not_found":
        return result

    # Not terminal — schedule the next poll.
    raise self.retry(countdown=_LOGISTICS_POLL_INTERVAL)


@celery_app.task(
    name="app.modules.fulfillment.tasks.poll_new_orders_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    queue="fulfillment",
)
def poll_new_orders_task(self, lookback_minutes: int | None = None) -> dict[str, Any]:
    """Fallback ingestion: poll 抖店 for new paid orders and fulfill them.

    Complements the webhook path; ingestion is idempotent so duplicate
    delivery (webhook + poll) is safe.

    Args:
        lookback_minutes: Window to look back; defaults to config.

    Returns:
        Counts of polled and dispatched orders.
    """
    window = (
        lookback_minutes
        if lookback_minutes is not None
        else settings.FULFILLMENT_ORDER_POLL_LOOKBACK_MINUTES
    )
    logger.info("[Fulfillment] poll_new_orders (lookback=%dmin)", window)

    async def _execute() -> list[dict[str, Any]]:
        service, session = await _build_service()
        try:
            orders = await service.fetch_new_douyin_orders(window)
            return orders
        finally:
            await service.close()
            await session.close()

    try:
        raw_orders = _run_async(_execute())
    except Exception as exc:
        logger.error("[Fulfillment] poll_new_orders failed: %s", exc)
        raise self.retry(exc=exc)

    dispatched = 0
    for raw in raw_orders:
        process_order_task.apply_async(args=[raw], countdown=dispatched * 2)
        dispatched += 1

    return {"polled": len(raw_orders), "dispatched": dispatched}


@celery_app.task(
    name="app.modules.fulfillment.tasks.refresh_active_logistics_task",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    queue="fulfillment",
)
def refresh_active_logistics_task(self) -> dict[str, Any]:
    """Periodically re-poll logistics for all in-flight supplier orders.

    A safety net in case a per-order tracking chain was interrupted; picks up
    any CREATED/PAID/SHIPPED supplier orders with a 1688 order id.

    Returns:
        Count of supplier orders re-dispatched for tracking.
    """
    logger.info("[Fulfillment] refresh_active_logistics")

    async def _execute() -> list[str]:
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models.fulfillment import SupplierOrder, SupplierOrderStatus

        async with async_session_factory() as session:
            res = await session.execute(
                select(SupplierOrder).where(
                    SupplierOrder.status.in_(
                        [
                            SupplierOrderStatus.CREATED,
                            SupplierOrderStatus.PAID,
                            SupplierOrderStatus.SHIPPED,
                        ]
                    ),
                    SupplierOrder.alibaba_order_id.isnot(None),
                )
            )
            return [str(so.id) for so in res.scalars().all()]

    try:
        ids = _run_async(_execute())
    except Exception as exc:
        logger.error("[Fulfillment] refresh_active_logistics failed: %s", exc)
        raise self.retry(exc=exc)

    for idx, sid in enumerate(ids):
        track_logistics_task.apply_async(args=[sid], countdown=idx * 2)

    return {"refreshed": len(ids)}
