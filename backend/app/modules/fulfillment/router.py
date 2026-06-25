"""FastAPI router for the Fulfillment module.

Exposes both flows:
    Flow 1: POST /source-and-list — match a 1688 supply, price, list on 抖店.
    Flow 2: POST /webhook/douyin-order — receive 抖店 order pushes (signed),
            plus order list/detail/manual-fulfill and listing list endpoints.

The webhook is the primary order-ingestion path (verified by a shared
secret HMAC); a Celery beat poller is the fallback. Both converge on the
idempotent process_order_task.
"""

import hashlib
import hmac
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.fulfillment import (
    ListingStatus,
    Order,
    OrderStatus,
    SourcedListing,
)

router = APIRouter(prefix="/fulfillment", tags=["fulfillment"])


# -- Request / response schemas ----------------------------------------------


class SourceAndListRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    category: str = Field(default="", max_length=256)
    image_url: str | None = Field(default=None, max_length=1024)
    description: str = Field(default="", max_length=4000)
    asset_urls: list[str] = Field(default_factory=list)
    source_candidate_id: str | None = Field(default=None)
    auto_publish: bool = Field(default=False)
    async_mode: bool = Field(
        default=True,
        description="Run via Celery (recommended). If false, runs inline.",
    )


class SourceAndListResponse(BaseModel):
    mode: str
    task_id: str | None = None
    listing_id: str | None = None
    status: str | None = None
    match_score: float | None = None
    sell_price: float | None = None
    achieved_margin: float | None = None
    douyin_product_id: str | None = None
    error_message: str | None = None


class ListingResponse(BaseModel):
    id: str
    title: str
    category: str
    status: str
    alibaba_offer_id: str | None
    supplier_name: str
    supplier_url: str
    match_score: float
    wholesale_price: float
    landed_cost: float
    sell_price: float
    target_margin: float
    achieved_margin: float
    douyin_product_id: str | None
    error_message: str | None
    created_at: datetime


class SupplierOrderResponse(BaseModel):
    id: str
    alibaba_order_id: str | None
    alibaba_offer_id: str | None
    quantity: int
    total_amount: float
    status: str
    tracking_no: str | None
    logistics_company: str | None


class OrderResponse(BaseModel):
    id: str
    listing_id: str | None
    douyin_order_id: str
    douyin_product_id: str | None
    sku_id: str | None
    quantity: int
    buyer_paid_amount: float
    status: str
    error_message: str | None
    fulfilled_at: datetime | None
    created_at: datetime
    supplier_order: SupplierOrderResponse | None = None


class WebhookAck(BaseModel):
    code: int = 0
    message: str = "success"
    task_id: str | None = None


# -- Helpers -----------------------------------------------------------------


def _listing_to_response(listing: SourcedListing) -> ListingResponse:
    return ListingResponse(
        id=str(listing.id),
        title=listing.title,
        category=listing.category,
        status=listing.status.value
        if isinstance(listing.status, ListingStatus)
        else listing.status,
        alibaba_offer_id=listing.alibaba_offer_id,
        supplier_name=listing.supplier_name,
        supplier_url=listing.supplier_url,
        match_score=float(listing.match_score or 0.0),
        wholesale_price=float(listing.wholesale_price or 0.0),
        landed_cost=float(listing.landed_cost or 0.0),
        sell_price=float(listing.sell_price or 0.0),
        target_margin=float(listing.target_margin or 0.0),
        achieved_margin=float(listing.achieved_margin or 0.0),
        douyin_product_id=listing.douyin_product_id,
        error_message=listing.error_message,
        created_at=listing.created_at,
    )


def _order_to_response(order: Order) -> OrderResponse:
    so = order.supplier_order
    supplier_resp = None
    if so is not None:
        supplier_resp = SupplierOrderResponse(
            id=str(so.id),
            alibaba_order_id=so.alibaba_order_id,
            alibaba_offer_id=so.alibaba_offer_id,
            quantity=so.quantity,
            total_amount=float(so.total_amount or 0.0),
            status=so.status.value if hasattr(so.status, "value") else so.status,
            tracking_no=so.tracking_no,
            logistics_company=so.logistics_company,
        )
    return OrderResponse(
        id=str(order.id),
        listing_id=str(order.listing_id) if order.listing_id else None,
        douyin_order_id=order.douyin_order_id,
        douyin_product_id=order.douyin_product_id,
        sku_id=order.sku_id,
        quantity=order.quantity,
        buyer_paid_amount=float(order.buyer_paid_amount or 0.0),
        status=order.status.value
        if isinstance(order.status, OrderStatus)
        else order.status,
        error_message=order.error_message,
        fulfilled_at=order.fulfilled_at,
        created_at=order.created_at,
        supplier_order=supplier_resp,
    )


def _verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verify the 抖店 order-push HMAC-SHA256 signature.

    When no secret is configured the check is skipped (dev-friendly), but a
    warning-worthy posture; configure DOUYIN_ORDER_WEBHOOK_SECRET in prod.
    """
    secret = settings.DOUYIN_ORDER_WEBHOOK_SECRET
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# -- Flow 1: source -> list --------------------------------------------------


@router.post("/source-and-list", response_model=SourceAndListResponse)
async def source_and_list(
    body: SourceAndListRequest,
    db: AsyncSession = Depends(get_db),
) -> SourceAndListResponse:
    """Find a same-source 1688 supply, price for target margin, list on 抖店.

    By default this is dispatched to Celery (async_mode=true) and returns a
    task id. Set async_mode=false to run inline and get the listing outcome.
    """
    payload = {
        "title": body.title,
        "category": body.category,
        "image_url": body.image_url,
        "description": body.description,
        "asset_urls": body.asset_urls,
        "source_candidate_id": body.source_candidate_id,
        "auto_publish": body.auto_publish,
    }

    if body.async_mode:
        from app.modules.fulfillment.tasks import source_and_list_task

        task = source_and_list_task.apply_async(args=[payload], queue="fulfillment")
        return SourceAndListResponse(mode="async", task_id=task.id, status="queued")

    # Inline execution.
    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.modules.fulfillment.service import FulfillmentService, SourceListingInput

    redis = await get_redis()
    rate_limiter = TokenBucketRateLimiter(redis=redis)
    service = FulfillmentService(db=db, rate_limiter=rate_limiter)
    try:
        listing = await service.source_and_list(
            SourceListingInput(
                title=body.title,
                category=body.category,
                image_url=body.image_url,
                description=body.description,
                asset_urls=body.asset_urls,
                source_candidate_id=body.source_candidate_id,
                auto_publish=body.auto_publish,
            )
        )
        await db.flush()
        return SourceAndListResponse(
            mode="inline",
            listing_id=str(listing.id),
            status=listing.status.value
            if isinstance(listing.status, ListingStatus)
            else listing.status,
            match_score=float(listing.match_score or 0.0),
            sell_price=float(listing.sell_price or 0.0),
            achieved_margin=float(listing.achieved_margin or 0.0),
            douyin_product_id=listing.douyin_product_id,
            error_message=listing.error_message,
        )
    finally:
        await service.close()


@router.get("/listings", response_model=list[ListingResponse])
async def list_listings(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[ListingResponse]:
    """List sourced listings, newest first, optionally filtered by status."""
    stmt = select(SourcedListing).order_by(SourcedListing.created_at.desc())
    if status_filter:
        stmt = stmt.where(SourcedListing.status == status_filter)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [_listing_to_response(li) for li in result.scalars().all()]


@router.get("/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
) -> ListingResponse:
    """Get a single sourced listing by id."""
    try:
        lid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id")

    result = await db.execute(select(SourcedListing).where(SourcedListing.id == lid))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _listing_to_response(listing)


# -- Flow 2: order webhook + management --------------------------------------


@router.post("/webhook/douyin-order", response_model=WebhookAck)
async def douyin_order_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> WebhookAck:
    """Receive a 抖店 order push, verify its signature, and dispatch fulfillment.

    Primary order-ingestion path. The payload may be a single order object or
    a list/envelope; we extract the order portion and hand it to the
    idempotent process_order_task. Returns immediately so 抖店 sees a fast ack.
    """
    raw = await request.body()
    if not _verify_webhook_signature(raw, x_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    order_payload = _extract_order_payload(body)
    if not order_payload:
        return WebhookAck(code=0, message="ignored: no order payload")

    from app.modules.fulfillment.tasks import process_order_task

    task = process_order_task.apply_async(args=[order_payload], queue="fulfillment")
    return WebhookAck(code=0, message="accepted", task_id=task.id)


def _extract_order_payload(body: Any) -> dict[str, Any] | None:
    """Pull the order dict out of various 抖店 push envelope shapes."""
    if isinstance(body, list):
        return body[0] if body else None
    if not isinstance(body, dict):
        return None
    # Common 抖店 push envelope: {"tag": "...", "data": {...or "..."}}
    data = body.get("data", body)
    if isinstance(data, str):
        import json

        try:
            data = json.loads(data)
        except ValueError:
            return None
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        # Some pushes wrap the order under "order" / "p_extra".
        inner = data.get("order")
        if isinstance(inner, dict):
            return inner
        return data
    return None


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[OrderResponse]:
    """List orders, newest first, optionally filtered by status."""
    stmt = (
        select(Order)
        .options(selectinload(Order.supplier_order))
        .order_by(Order.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [_order_to_response(o) for o in result.scalars().unique().all()]


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Get a single order with its supplier order, by internal id."""
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order id")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.supplier_order))
        .where(Order.id == oid)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_response(order)


@router.post("/orders/{order_id}/fulfill", response_model=OrderResponse)
async def fulfill_order_manually(
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Manually (re)place the 1688 order for an ingested 抖店 order.

    Useful when auto-fulfillment was skipped (e.g. no linked offer at ingest
    time) or to retry a failed fulfillment after fixing the listing link.
    """
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order id")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.supplier_order))
        .where(Order.id == oid)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.modules.fulfillment.service import FulfillmentService

    redis = await get_redis()
    rate_limiter = TokenBucketRateLimiter(redis=redis)
    service = FulfillmentService(db=db, rate_limiter=rate_limiter)
    try:
        supplier_order = await service.fulfill_order(order)
        await db.flush()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    finally:
        await service.close()

    # Dispatch logistics tracking when the 1688 order was created.
    if supplier_order.alibaba_order_id:
        from app.modules.fulfillment.tasks import track_logistics_task

        track_logistics_task.apply_async(
            args=[str(supplier_order.id)], countdown=600, queue="fulfillment"
        )

    await db.refresh(order, attribute_names=["supplier_order"])
    return _order_to_response(order)


@router.get("/stats", response_model=dict)
async def fulfillment_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Summary counters for listings and orders by status."""
    listing_rows = await db.execute(
        select(SourcedListing.status, func.count(SourcedListing.id)).group_by(
            SourcedListing.status
        )
    )
    order_rows = await db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )

    def _key(v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)

    return {
        "listings_by_status": {_key(s): c for s, c in listing_rows.all()},
        "orders_by_status": {_key(s): c for s, c in order_rows.all()},
    }
