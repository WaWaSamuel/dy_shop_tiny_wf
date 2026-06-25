"""Fulfillment service: end-to-end sourcing/listing and order fulfillment.

Flow 1 (source -> list):
    selected product -> find same-source 1688 supplier (image+keyword fusion)
    -> price for target margin -> assemble SKU/price + ad assets
    -> list to 抖店 via the existing ProductUploadService.

Flow 2 (order -> 1688 order -> logistics):
    ingest 抖店 order (webhook/poll) -> place matching 1688 order
    -> poll logistics -> push shipment back to 抖店.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import TokenBucketRateLimiter
from app.core.security import sign_request
from app.models.fulfillment import (
    ListingStatus,
    LogisticsTrack,
    Order,
    OrderStatus,
    SourcedListing,
    SupplierOrder,
    SupplierOrderStatus,
)
from app.modules.product_upload.service import ProductInput, ProductUploadService

from .alibaba_order import AlibabaOrderClient
from .matcher import SourceMatcher
from .pricing import PricingEngine

logger = logging.getLogger(__name__)

DOUYIN_API_BASE = "https://openapi-fxg.jinritemai.com"

# Terminal logistics statuses that stop polling.
_DELIVERED_STATUSES = {"delivered", "signed", "SIGN", "已签收"}


@dataclass
class SourceListingInput:
    """Input for the source -> list flow (a selected product)."""

    title: str
    category: str = ""
    image_url: str | None = None
    description: str = ""
    asset_urls: list[str] = field(default_factory=list)
    source_candidate_id: str | None = None
    auto_publish: bool = False


class FulfillmentService:
    """Orchestrates sourcing/listing and 抖店<->1688 order fulfillment."""

    def __init__(self, db: AsyncSession, rate_limiter: TokenBucketRateLimiter) -> None:
        self.db = db
        self.rate_limiter = rate_limiter
        self.matcher = SourceMatcher(rate_limiter)
        self.pricing = PricingEngine()
        self.alibaba = AlibabaOrderClient(rate_limiter)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=DOUYIN_API_BASE, timeout=30.0)
        return self._client

    async def close(self) -> None:
        await self.matcher.close()
        await self.alibaba.close()
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─────────────────────────────────────────────────────────────────────
    # Flow 1: source -> price -> list
    # ─────────────────────────────────────────────────────────────────────

    async def source_and_list(self, data: SourceListingInput) -> SourcedListing:
        """Find a same-source 1688 supply, price it, and list on 抖店.

        Returns the persisted SourcedListing reflecting the outcome (matched,
        no_source, listed, or listing_failed).
        """
        listing = SourcedListing(
            title=data.title,
            category=data.category,
            asset_urls=data.asset_urls,
            target_margin=self.pricing.target_margin,
            status=ListingStatus.MATCHING,
        )
        if data.source_candidate_id:
            try:
                listing.source_candidate_id = uuid.UUID(data.source_candidate_id)
            except ValueError:
                logger.warning("Invalid source_candidate_id: %s", data.source_candidate_id)
        self.db.add(listing)
        await self.db.flush()

        # Step 1: same-source matching (image + keyword fusion).
        match = await self.matcher.find_best_match(
            title=data.title, image_url=data.image_url
        )
        if match is None:
            listing.status = ListingStatus.NO_SOURCE
            listing.error_message = "No qualifying same-source 1688 supplier found"
            await self.db.flush()
            logger.info("No 1688 source for '%s'", data.title[:40])
            return listing

        supplier = match.supplier
        listing.alibaba_offer_id = supplier.supplier_id and self._extract_offer_id(supplier)
        listing.supplier_name = supplier.supplier_name
        listing.supplier_url = supplier.product_url
        listing.delivery_location = supplier.delivery_location
        listing.match_score = match.fused_score
        listing.wholesale_price = supplier.wholesale_price

        # Step 2: pricing for target margin.
        quote = self.pricing.quote(
            wholesale_price=supplier.wholesale_price,
            delivery_loc=supplier.delivery_location,
            category=data.category or "default",
        )
        listing.landed_cost = quote.landed_cost
        listing.sell_price = quote.sell_price
        listing.achieved_margin = quote.achieved_margin

        if not quote.feasible:
            listing.status = ListingStatus.NO_SOURCE
            listing.error_message = quote.reason
            await self.db.flush()
            logger.info("Pricing infeasible for '%s': %s", data.title[:40], quote.reason)
            return listing

        listing.status = ListingStatus.MATCHED
        listing.sku_mapping = {
            "offer_id": listing.alibaba_offer_id,
            "wholesale_price": supplier.wholesale_price,
            "moq": supplier.moq,
        }
        await self.db.flush()

        # Step 3: assemble + list on 抖店.
        await self._list_on_douyin(listing, data, quote.sell_price)
        return listing

    async def _list_on_douyin(
        self,
        listing: SourcedListing,
        data: SourceListingInput,
        sell_price: float,
    ) -> None:
        """Build a ProductInput from the sourced data and submit to 抖店."""
        listing.status = ListingStatus.LISTING
        await self.db.flush()

        images = data.asset_urls or ([data.image_url] if data.image_url else [])
        sku = {
            "name": data.title,
            "price": sell_price,
            "market_price": round(sell_price * 1.3, 2),
            "stock": 999,
            "image_url": data.image_url,
        }
        product_input = ProductInput(
            name=data.title,
            description=data.description,
            images=images,
            category_id=None,  # auto-matched by ProductUploadService
            skus=[sku],
            price=sell_price,
            market_price=sku["market_price"],
            stock=999,
            auto_publish=data.auto_publish,
        )

        upload_service = ProductUploadService(db=self.db)
        try:
            product = await upload_service.create_product(product_input)
            listing.product_id = product.id
            listing.douyin_product_id = product.douyin_product_id
            listing.status = ListingStatus.LISTED
            logger.info(
                "Listed '%s' on 抖店: product_id=%s price=%.2f margin=%.1f%%",
                data.title[:40],
                product.douyin_product_id,
                sell_price,
                listing.achieved_margin * 100.0,
            )
        except Exception as e:
            listing.status = ListingStatus.LISTING_FAILED
            listing.error_message = str(e)
            logger.error("Listing failed for '%s': %s", data.title[:40], e)
        finally:
            await upload_service.close()
        await self.db.flush()

    @staticmethod
    def _extract_offer_id(supplier) -> str:
        """Derive the 1688 offer id from a supplier result.

        The search result's offer id is embedded in the product URL
        (e.g. .../offer/<id>.html); fall back to the supplier id.
        """
        url = supplier.product_url or ""
        if "offer/" in url:
            tail = url.split("offer/", 1)[1]
            digits = "".join(c for c in tail if c.isdigit())
            if digits:
                return digits
        return str(supplier.supplier_id)

    # ─────────────────────────────────────────────────────────────────────
    # Flow 2: ingest order -> 1688 order -> logistics
    # ─────────────────────────────────────────────────────────────────────

    async def ingest_order(self, payload: dict[str, Any]) -> Order:
        """Create (idempotently) an Order from a 抖店 order payload.

        Args:
            payload: Normalized 抖店 order fields (see _normalize_douyin_order).

        Returns:
            The persisted Order (existing record if already ingested).
        """
        normalized = self._normalize_douyin_order(payload)
        douyin_order_id = normalized["douyin_order_id"]

        existing = await self.db.execute(
            select(Order).where(Order.douyin_order_id == douyin_order_id)
        )
        order = existing.scalar_one_or_none()
        if order is not None:
            return order

        # Link to a listing by 抖店 product id (gives us the 1688 offer).
        listing_id = None
        if normalized.get("douyin_product_id"):
            res = await self.db.execute(
                select(SourcedListing).where(
                    SourcedListing.douyin_product_id == normalized["douyin_product_id"]
                )
            )
            listing = res.scalar_one_or_none()
            if listing is not None:
                listing_id = listing.id

        order = Order(
            listing_id=listing_id,
            douyin_order_id=douyin_order_id,
            douyin_product_id=normalized.get("douyin_product_id"),
            sku_id=normalized.get("sku_id"),
            quantity=normalized.get("quantity", 1),
            buyer_paid_amount=normalized.get("buyer_paid_amount", 0.0),
            receiver_info=normalized.get("receiver_info", {}),
            status=OrderStatus.RECEIVED,
        )
        self.db.add(order)
        await self.db.flush()
        logger.info("Ingested 抖店 order %s (listing=%s)", douyin_order_id, listing_id)
        return order

    async def fulfill_order(self, order: Order) -> SupplierOrder:
        """Place the matching 1688 order for an ingested 抖店 order.

        Returns the SupplierOrder (created or existing).
        """
        if order.supplier_order is not None:
            return order.supplier_order

        order.status = OrderStatus.SOURCING
        await self.db.flush()

        listing = None
        if order.listing_id is not None:
            res = await self.db.execute(
                select(SourcedListing).where(SourcedListing.id == order.listing_id)
            )
            listing = res.scalar_one_or_none()

        offer_id = listing.alibaba_offer_id if listing else None
        if not offer_id:
            order.status = OrderStatus.FULFILL_FAILED
            order.error_message = "No linked 1688 offer for this order"
            await self.db.flush()
            raise ValueError(order.error_message)

        result = await self.alibaba.create_order(
            offer_id=offer_id,
            quantity=order.quantity,
            receiver=order.receiver_info,
            sku_id=order.sku_id,
            message=f"抖店订单 {order.douyin_order_id}",
        )

        supplier_order = SupplierOrder(
            order_id=order.id,
            alibaba_offer_id=offer_id,
            quantity=order.quantity,
            raw_response=result.raw,
        )
        if result.success:
            supplier_order.alibaba_order_id = result.alibaba_order_id
            supplier_order.total_amount = result.total_amount
            supplier_order.status = SupplierOrderStatus.CREATED
            order.status = OrderStatus.SOURCED
            order.fulfilled_at = datetime.utcnow()
        else:
            supplier_order.status = SupplierOrderStatus.FAILED
            supplier_order.error_message = result.error_message
            order.status = OrderStatus.FULFILL_FAILED
            order.error_message = result.error_message

        self.db.add(supplier_order)
        await self.db.flush()
        logger.info(
            "1688 order for 抖店 %s: success=%s id=%s",
            order.douyin_order_id,
            result.success,
            result.alibaba_order_id,
        )
        return supplier_order

    async def track_logistics(self, supplier_order: SupplierOrder) -> LogisticsTrack | None:
        """Poll 1688 logistics for a supplier order and persist a snapshot.

        On first tracking-number availability, pushes the shipment back to
        抖店. Returns the new LogisticsTrack, or None if no order id yet.
        """
        if not supplier_order.alibaba_order_id:
            return None

        trace = await self.alibaba.get_logistics_trace(supplier_order.alibaba_order_id)
        if not trace.success:
            logger.warning(
                "Logistics trace failed for 1688 order %s: %s",
                supplier_order.alibaba_order_id,
                trace.error_message,
            )
            return None

        track = LogisticsTrack(
            supplier_order_id=supplier_order.id,
            tracking_no=trace.tracking_no,
            logistics_company=trace.logistics_company,
            status=trace.status,
            trace_detail=trace.steps,
        )
        self.db.add(track)

        # Mirror summary onto the supplier order.
        if trace.tracking_no:
            supplier_order.tracking_no = trace.tracking_no
            supplier_order.logistics_company = trace.logistics_company
            if supplier_order.status in (
                SupplierOrderStatus.CREATED,
                SupplierOrderStatus.PAID,
            ):
                supplier_order.status = SupplierOrderStatus.SHIPPED

        # Load the parent 抖店 order to update status / sync shipment.
        res = await self.db.execute(
            select(Order).where(Order.id == supplier_order.order_id)
        )
        order = res.scalar_one_or_none()

        delivered = trace.status in _DELIVERED_STATUSES
        if order is not None:
            if delivered:
                order.status = OrderStatus.DELIVERED
                supplier_order.status = SupplierOrderStatus.SUCCESS
            elif trace.tracking_no:
                order.status = OrderStatus.SHIPPED

            # Push shipment to 抖店 once we have a tracking number, once.
            if trace.tracking_no and order.status in (
                OrderStatus.SHIPPED,
                OrderStatus.DELIVERED,
            ):
                synced = await self._sync_shipment_to_douyin(order, trace)
                track.synced_to_douyin = synced

        await self.db.flush()
        return track

    async def _sync_shipment_to_douyin(self, order: Order, trace) -> bool:
        """Push the supplier shipment to 抖店 via order.logisticsAdd."""
        if not settings.DOUYIN_ACCESS_TOKEN:
            logger.info("抖店 token not configured; skipping shipment sync")
            return False

        path = "/order/logisticsAdd"
        params = {"access_token": settings.DOUYIN_ACCESS_TOKEN}
        payload = {
            "order_id": order.douyin_order_id,
            "company_name": trace.logistics_company,
            "logistics_code": trace.tracking_no,
            "tracking_no": trace.tracking_no,
        }
        body = json.dumps(payload, ensure_ascii=False)
        params.update(sign_request("POST", path, params, body=body))

        try:
            client = await self._get_client()
            response = await client.post(path, params=params, json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error("抖店 shipment sync error for %s: %s", order.douyin_order_id, e)
            return False

        if data.get("err_no") not in (0, None):
            logger.error(
                "抖店 shipment sync rejected for %s: %s",
                order.douyin_order_id,
                data.get("message"),
            )
            return False

        logger.info(
            "Synced shipment to 抖店 for order %s (tracking=%s)",
            order.douyin_order_id,
            trace.tracking_no,
        )
        return True

    # ─────────────────────────────────────────────────────────────────────
    # 抖店 order polling (fallback ingestion)
    # ─────────────────────────────────────────────────────────────────────

    async def fetch_new_douyin_orders(self, lookback_minutes: int) -> list[dict[str, Any]]:
        """Poll 抖店 for recently-paid orders (fallback to webhook).

        Returns a list of raw 抖店 order dicts; ingestion/normalization is
        handled by ingest_order.
        """
        if not settings.DOUYIN_ACCESS_TOKEN:
            logger.info("抖店 token not configured; skipping order poll")
            return []

        path = "/order/searchList"
        params = {"access_token": settings.DOUYIN_ACCESS_TOKEN}
        start_ts = int(datetime.utcnow().timestamp()) - lookback_minutes * 60
        payload = {
            "order_status": 2,  # paid / to-ship
            "create_time_start": start_ts,
            "size": 50,
            "page": 0,
        }
        body = json.dumps(payload, ensure_ascii=False)
        params.update(sign_request("POST", path, params, body=body))

        try:
            client = await self._get_client()
            response = await client.post(path, params=params, json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error("抖店 order poll error: %s", e)
            return []

        if data.get("err_no") not in (0, None):
            logger.error("抖店 order poll rejected: %s", data.get("message"))
            return []

        return data.get("data", {}).get("order_list", []) or []

    @staticmethod
    def _normalize_douyin_order(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize a 抖店 order (webhook or poll shape) to our fields."""
        order_id = str(
            payload.get("order_id")
            or payload.get("shop_order_id")
            or payload.get("p_id", "")
        )
        # 抖店 nests SKU lines under sku_order_list; take the first line.
        sku_lines = payload.get("sku_order_list") or payload.get("sku_orders") or []
        first = sku_lines[0] if sku_lines else payload

        product_id = str(first.get("product_id") or payload.get("product_id") or "") or None
        sku_id = str(first.get("sku_id") or payload.get("sku_id") or "") or None
        quantity = int(first.get("item_num") or payload.get("quantity") or 1)
        paid_cents = (
            first.get("pay_amount")
            or payload.get("pay_amount")
            or payload.get("order_amount")
            or 0
        )
        buyer_paid = round(float(paid_cents) / 100.0, 2) if paid_cents else 0.0

        receiver = payload.get("receiver_info") or payload.get("address") or {}
        normalized_receiver = {
            "name": receiver.get("name") or receiver.get("post_receiver", ""),
            "phone": receiver.get("phone") or receiver.get("post_tel", ""),
            "province": receiver.get("province") or receiver.get("post_province", ""),
            "city": receiver.get("city") or receiver.get("post_city", ""),
            "area": receiver.get("area")
            or receiver.get("town")
            or receiver.get("post_area", ""),
            "address": receiver.get("address") or receiver.get("post_addr", ""),
            "post_code": receiver.get("post_code", ""),
        }

        return {
            "douyin_order_id": order_id,
            "douyin_product_id": product_id,
            "sku_id": sku_id,
            "quantity": quantity,
            "buyer_paid_amount": buyer_paid,
            "receiver_info": normalized_receiver,
        }
