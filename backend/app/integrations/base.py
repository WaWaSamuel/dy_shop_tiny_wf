"""Abstract base classes for all integration providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseSourcingProvider(ABC):
    """Abstract base class for product sourcing providers (e.g., 1688, AliExpress)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether this provider is currently enabled."""
        return True

    @abstractmethod
    async def search_products(
        self,
        *,
        keyword: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for products on this sourcing platform.

        Args:
            keyword: Search keyword.
            category: Optional category filter.
            min_price: Minimum price filter.
            max_price: Maximum price filter.
            page: Page number.
            page_size: Results per page.

        Returns:
            List of raw product dictionaries from this provider.
        """
        ...

    @abstractmethod
    async def get_product_detail(self, external_id: str) -> Optional[dict[str, Any]]:
        """Get detailed product information by external ID.

        Args:
            external_id: Product ID in the provider's system.

        Returns:
            Product detail dictionary or None if not found.
        """
        ...

    @abstractmethod
    async def get_supplier_info(self, supplier_id: str) -> Optional[dict[str, Any]]:
        """Get supplier/vendor information.

        Args:
            supplier_id: Supplier ID in the provider's system.

        Returns:
            Supplier info dictionary or None.
        """
        ...

    async def check_availability(self, external_id: str) -> bool:
        """Check if a product is still available for sourcing.

        Default implementation calls get_product_detail.
        """
        detail = await self.get_product_detail(external_id)
        return detail is not None and detail.get("available", False)


class BaseSelectionProvider(ABC):
    """Abstract base class for product selection/curation providers.

    Selection providers offer curated product recommendations,
    trending analysis, and market intelligence.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        ...

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    async def get_trending_products(
        self,
        *,
        category: Optional[str] = None,
        time_range: str = "7d",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get trending/hot products.

        Args:
            category: Optional category filter.
            time_range: Time range for trending data (e.g., '24h', '7d', '30d').
            limit: Max number of results.

        Returns:
            List of trending product data.
        """
        ...

    @abstractmethod
    async def get_recommendations(
        self,
        *,
        based_on: Optional[list[str]] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get product recommendations.

        Args:
            based_on: Optional list of product IDs to base recommendations on.
            category: Optional category filter.
            limit: Max recommendations.

        Returns:
            List of recommended product data.
        """
        ...


class BasePlatformProvider(ABC):
    """Abstract base class for e-commerce platform integrations (e.g., Douyin, Taobao)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        ...

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    async def publish_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Publish a product listing to the platform.

        Args:
            product_data: Product data formatted for this platform.

        Returns:
            Publication result including external listing ID.
        """
        ...

    @abstractmethod
    async def update_product(
        self, external_id: str, product_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing product listing.

        Args:
            external_id: Platform-specific product ID.
            product_data: Updated product data.

        Returns:
            Update result.
        """
        ...

    @abstractmethod
    async def get_orders(
        self,
        *,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Fetch orders from the platform.

        Args:
            status: Optional order status filter.
            start_time: ISO format start time.
            end_time: ISO format end time.
            page: Page number.
            page_size: Results per page.

        Returns:
            Dictionary with orders list and pagination info.
        """
        ...

    @abstractmethod
    async def sync_inventory(
        self, inventory_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Sync inventory levels to the platform.

        Args:
            inventory_data: List of SKU-quantity mappings.

        Returns:
            Sync result with success/failure counts.
        """
        ...

    @abstractmethod
    async def get_product_stats(self, external_id: str) -> dict[str, Any]:
        """Get product performance stats from platform.

        Args:
            external_id: Platform product ID.

        Returns:
            Stats including views, sales, conversion rate, etc.
        """
        ...


class BaseLogisticsProvider(ABC):
    """Abstract base class for logistics/shipping providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        ...

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    async def create_shipment(
        self, shipment_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new shipment/waybill.

        Args:
            shipment_data: Shipment details (sender, recipient, items, etc.).

        Returns:
            Shipment result with tracking number.
        """
        ...

    @abstractmethod
    async def track_shipment(self, tracking_number: str) -> dict[str, Any]:
        """Get tracking information for a shipment.

        Args:
            tracking_number: The tracking/waybill number.

        Returns:
            Tracking info with status history.
        """
        ...

    @abstractmethod
    async def estimate_shipping(
        self, *, origin: str, destination: str, weight_kg: float
    ) -> dict[str, Any]:
        """Estimate shipping cost and time.

        Args:
            origin: Origin address or region code.
            destination: Destination address or region code.
            weight_kg: Package weight in kg.

        Returns:
            Estimate with cost, currency, and estimated days.
        """
        ...

    @abstractmethod
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel a shipment if possible.

        Returns:
            True if cancellation was successful.
        """
        ...
