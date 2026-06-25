"""Order service - order management and auto-fulfillment logic."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.pagination import PaginatedResult, paginate_query


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDING = "refunding"
    REFUNDED = "refunded"


class FulfillmentStrategy(str, Enum):
    MANUAL = "manual"
    AUTO_SHIP = "auto_ship"
    DROP_SHIP = "drop_ship"
    DIGITAL = "digital"


# Valid status transitions
STATUS_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.PENDING: [OrderStatus.PAID, OrderStatus.CANCELLED],
    OrderStatus.PAID: [OrderStatus.PROCESSING, OrderStatus.CANCELLED, OrderStatus.REFUNDING],
    OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED, OrderStatus.REFUNDING],
    OrderStatus.DELIVERED: [OrderStatus.COMPLETED, OrderStatus.REFUNDING],
    OrderStatus.COMPLETED: [OrderStatus.REFUNDING],
    OrderStatus.REFUNDING: [OrderStatus.REFUNDED],
    OrderStatus.CANCELLED: [],
    OrderStatus.REFUNDED: [],
}


class OrderService:
    """Service for order management with auto-fulfillment logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_order(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new order from checkout data.

        Args:
            data: Order creation payload including items, shipping info,
                  payment method, etc.

        Returns:
            Created order as dictionary.
        """
        from app.models.order import Order, OrderItem  # type: ignore[import]

        # Calculate totals
        items_data = data.get("items", [])
        subtotal = sum(
            item["price"] * item["quantity"] for item in items_data
        )
        shipping_fee = data.get("shipping_fee", 0.0)
        discount = data.get("discount", 0.0)
        total = subtotal + shipping_fee - discount

        order = Order(
            user_id=data["user_id"],
            platform=data.get("platform", "internal"),
            platform_order_id=data.get("platform_order_id"),
            status=OrderStatus.PENDING.value,
            fulfillment_strategy=data.get(
                "fulfillment_strategy", FulfillmentStrategy.MANUAL.value
            ),
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            discount=discount,
            total=total,
            shipping_address=data.get("shipping_address", {}),
            buyer_note=data.get("buyer_note", ""),
            metadata=data.get("metadata", {}),
        )
        self.db.add(order)
        await self.db.flush()

        # Create order items
        for item_data in items_data:
            item = OrderItem(
                order_id=order.id,
                product_id=item_data["product_id"],
                sku_id=item_data.get("sku_id"),
                title=item_data["title"],
                price=item_data["price"],
                quantity=item_data["quantity"],
                image=item_data.get("image", ""),
            )
            self.db.add(item)

        await self.db.flush()
        await self.db.refresh(order)
        return self._serialize(order)

    async def get_order(self, order_id: UUID) -> Optional[dict[str, Any]]:
        """Get order by ID with items."""
        from app.models.order import Order  # type: ignore[import]

        stmt = select(Order).where(Order.id == order_id)
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            return None
        return self._serialize(order)

    async def update_order_status(
        self, order_id: UUID, new_status: OrderStatus, *, operator: str = "system"
    ) -> Optional[dict[str, Any]]:
        """Transition order to a new status with validation.

        Args:
            order_id: Order UUID.
            new_status: Target status.
            operator: Who triggered the transition.

        Returns:
            Updated order or None if invalid transition.

        Raises:
            ValueError: If transition is not allowed.
        """
        from app.models.order import Order  # type: ignore[import]

        stmt = select(Order).where(Order.id == order_id)
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            return None

        current_status = OrderStatus(order.status)
        allowed = STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {current_status.value} to {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        order.status = new_status.value
        order.updated_at = datetime.utcnow()

        # Record status history
        if not order.metadata:
            order.metadata = {}
        history = order.metadata.get("status_history", [])
        history.append({
            "from": current_status.value,
            "to": new_status.value,
            "operator": operator,
            "timestamp": datetime.utcnow().isoformat(),
        })
        order.metadata["status_history"] = history

        await self.db.flush()
        await self.db.refresh(order)

        # Trigger auto-fulfillment if applicable
        await self._check_auto_fulfillment(order)

        return self._serialize(order)

    async def _check_auto_fulfillment(self, order: Any) -> None:
        """Check and execute auto-fulfillment logic based on order strategy.

        Auto-fulfillment triggers:
        - PAID + AUTO_SHIP -> automatically move to PROCESSING and create shipment
        - PAID + DIGITAL -> immediately mark as COMPLETED
        - PAID + DROP_SHIP -> forward order to supplier
        """
        if order.status != OrderStatus.PAID.value:
            return

        strategy = FulfillmentStrategy(order.fulfillment_strategy)

        if strategy == FulfillmentStrategy.AUTO_SHIP:
            order.status = OrderStatus.PROCESSING.value
            order.updated_at = datetime.utcnow()
            # TODO: Trigger warehouse picking/packing via logistics integration
            await self.db.flush()

        elif strategy == FulfillmentStrategy.DIGITAL:
            order.status = OrderStatus.COMPLETED.value
            order.updated_at = datetime.utcnow()
            # TODO: Deliver digital goods (license keys, download links)
            await self.db.flush()

        elif strategy == FulfillmentStrategy.DROP_SHIP:
            order.status = OrderStatus.PROCESSING.value
            order.updated_at = datetime.utcnow()
            # TODO: Forward order to drop-ship supplier via sourcing integration
            await self.db.flush()

    async def list_orders(
        self,
        *,
        user_id: Optional[UUID] = None,
        status: Optional[OrderStatus] = None,
        platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """List orders with optional filters."""
        from app.models.order import Order  # type: ignore[import]

        stmt = select(Order)
        conditions = []

        if user_id:
            conditions.append(Order.user_id == user_id)
        if status:
            conditions.append(Order.status == status.value)
        if platform:
            conditions.append(Order.platform == platform)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Order.created_at.desc())
        return await paginate_query(self.db, stmt, page, page_size, self._serialize)

    async def cancel_order(
        self, order_id: UUID, reason: str = ""
    ) -> Optional[dict[str, Any]]:
        """Cancel an order with reason."""
        from app.models.order import Order  # type: ignore[import]

        stmt = select(Order).where(Order.id == order_id)
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            return None

        cancellable_statuses = [
            OrderStatus.PENDING.value,
            OrderStatus.PAID.value,
            OrderStatus.PROCESSING.value,
        ]
        if order.status not in cancellable_statuses:
            raise ValueError(
                f"Order in status '{order.status}' cannot be cancelled."
            )

        order.status = OrderStatus.CANCELLED.value
        order.updated_at = datetime.utcnow()
        if not order.metadata:
            order.metadata = {}
        order.metadata["cancel_reason"] = reason
        order.metadata["cancelled_at"] = datetime.utcnow().isoformat()

        await self.db.flush()
        await self.db.refresh(order)
        return self._serialize(order)

    async def sync_platform_orders(
        self, platform: str, orders_data: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Sync orders from external platform.

        Returns:
            Stats dict with created/updated/skipped counts.
        """
        from app.models.order import Order  # type: ignore[import]

        stats = {"created": 0, "updated": 0, "skipped": 0}

        for order_data in orders_data:
            platform_order_id = order_data.get("platform_order_id")
            if not platform_order_id:
                stats["skipped"] += 1
                continue

            stmt = select(Order).where(
                and_(
                    Order.platform == platform,
                    Order.platform_order_id == platform_order_id,
                )
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing order status
                if existing.status != order_data.get("status", existing.status):
                    existing.status = order_data["status"]
                    existing.updated_at = datetime.utcnow()
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                # Create new order
                order_data["platform"] = platform
                await self.create_order(order_data)
                stats["created"] += 1

        await self.db.flush()
        return stats

    @staticmethod
    def _serialize(order: Any) -> dict[str, Any]:
        """Convert order model to dictionary."""
        return {
            "id": str(order.id),
            "user_id": str(order.user_id) if order.user_id else None,
            "platform": order.platform,
            "platform_order_id": order.platform_order_id,
            "status": order.status,
            "fulfillment_strategy": order.fulfillment_strategy,
            "subtotal": float(order.subtotal) if order.subtotal else 0,
            "shipping_fee": float(order.shipping_fee) if order.shipping_fee else 0,
            "discount": float(order.discount) if order.discount else 0,
            "total": float(order.total) if order.total else 0,
            "shipping_address": order.shipping_address,
            "buyer_note": order.buyer_note,
            "metadata": order.metadata,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        }
