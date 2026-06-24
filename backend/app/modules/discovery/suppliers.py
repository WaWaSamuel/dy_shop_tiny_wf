"""1688 supplier matching and landed cost calculation.

Searches for suppliers via keyword and image-based search,
filters by quality criteria, and computes full landed cost.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded
from app.core.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


# Platform commission rates by top-level category (Douyin 抖店).
COMMISSION_RATES: dict[str, float] = {
    "服饰": 0.05,
    "美妆": 0.05,
    "食品": 0.05,
    "家居": 0.05,
    "数码": 0.06,
    "母婴": 0.05,
    "运动": 0.06,
    "箱包": 0.06,
    "鞋靴": 0.06,
    "珠宝": 0.08,
    "default": 0.05,
}

# Estimated packaging cost per unit by category.
PACKAGING_COST: dict[str, float] = {
    "服饰": 1.5,
    "美妆": 2.0,
    "食品": 2.5,
    "家居": 3.0,
    "数码": 3.5,
    "母婴": 2.0,
    "default": 2.0,
}

# Approximate domestic shipping cost (yuan) by origin region.
SHIPPING_COST_BY_REGION: dict[str, float] = {
    "浙江": 3.0,
    "广东": 3.5,
    "福建": 3.5,
    "江苏": 3.0,
    "上海": 3.0,
    "山东": 4.0,
    "河北": 4.5,
    "default": 5.0,
}


@dataclass(slots=True)
class SupplierResult:
    """A matched supplier from 1688 search."""

    supplier_name: str
    supplier_id: str
    product_title: str
    product_url: str
    wholesale_price: float
    moq: int
    supplier_rating: float
    transaction_count: int
    delivery_location: str
    image_url: str = ""
    sample_available: bool = False


@dataclass(slots=True)
class LandedCostBreakdown:
    """Full landed cost breakdown for a product."""

    wholesale_price: float
    shipping_cost: float
    commission_rate: float
    commission_amount: float
    packaging_cost: float
    total_landed_cost: float
    sell_price: float = 0.0
    gross_margin: float = 0.0
    margin_percentage: float = 0.0


class SupplierMatcher:
    """Searches and evaluates 1688 suppliers for product candidates.

    Uses the 1688 Open Platform API for keyword and image search,
    then filters results by quality thresholds.
    """

    BASE_URL = "https://gw.open.1688.com/openapi"

    def __init__(self, rate_limiter: TokenBucketRateLimiter) -> None:
        self.rate_limiter = rate_limiter
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def search_by_keyword(self, keyword: str, page: int = 1, page_size: int = 20) -> list[SupplierResult]:
        """Search 1688 suppliers by product keyword.

        Args:
            keyword: Search term (Chinese product name or keywords).
            page: Page number for pagination.
            page_size: Results per page (max 40).

        Returns:
            List of SupplierResult from search results.

        Raises:
            RateLimitExceeded: When API rate limit is hit.
        """
        await self.rate_limiter.acquire("alibaba_1688")

        client = await self._get_client()
        params = {
            "app_key": settings.ALIBABA_1688_APP_KEY,
            "keywords": keyword,
            "page_no": page,
            "page_size": min(page_size, 40),
            "sort_type": "booked_count",  # Sort by transaction volume
        }

        logger.info(
            "1688 keyword search: keyword=%s, page=%d",
            keyword,
            page,
            extra={"api_cost": "1688_search_keyword", "tokens_used": 1},
        )

        try:
            response = await client.get(
                f"{self.BASE_URL}/param2/1/com.alibaba.product/alibaba.product.search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "1688 keyword search failed: status=%d, keyword=%s",
                e.response.status_code,
                keyword,
            )
            return []
        except httpx.RequestError as e:
            logger.error("1688 keyword search network error: %s", str(e))
            return []

        return self._parse_search_results(data)

    async def search_by_image(self, image_url: str, page_size: int = 20) -> list[SupplierResult]:
        """Search 1688 suppliers by product image (以图搜图).

        Args:
            image_url: URL of the product image to match.
            page_size: Number of results to return.

        Returns:
            List of SupplierResult from image-matched results.
        """
        await self.rate_limiter.acquire("alibaba_1688")

        client = await self._get_client()
        params = {
            "app_key": settings.ALIBABA_1688_APP_KEY,
            "image_url": image_url,
            "page_size": min(page_size, 40),
        }

        logger.info(
            "1688 image search: image_url=%s",
            image_url[:80],
            extra={"api_cost": "1688_search_image", "tokens_used": 1},
        )

        try:
            response = await client.post(
                f"{self.BASE_URL}/param2/1/com.alibaba.product/alibaba.product.imageSearch",
                json=params,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "1688 image search failed: status=%d",
                e.response.status_code,
            )
            return []
        except httpx.RequestError as e:
            logger.error("1688 image search network error: %s", str(e))
            return []

        return self._parse_search_results(data)

    @staticmethod
    def filter_suppliers(
        results: list[SupplierResult],
        min_rating: float = 4.5,
        min_transactions: int = 1000,
    ) -> list[SupplierResult]:
        """Filter supplier results by quality criteria.

        Args:
            results: Raw search results to filter.
            min_rating: Minimum supplier rating (0-5 scale).
            min_transactions: Minimum historical transaction count.

        Returns:
            Filtered list meeting quality thresholds, sorted by rating descending.
        """
        filtered = [
            r
            for r in results
            if r.supplier_rating >= min_rating and r.transaction_count >= min_transactions
        ]
        filtered.sort(key=lambda x: (x.supplier_rating, x.transaction_count), reverse=True)
        return filtered

    @staticmethod
    def calculate_landed_cost(
        wholesale_price: float,
        delivery_loc: str,
        category: str,
        sell_price: float = 0.0,
    ) -> LandedCostBreakdown:
        """Calculate full landed cost including all fees.

        Components:
            - Wholesale unit price
            - Domestic shipping (origin-dependent)
            - Douyin platform commission (5-8% of sell price)
            - Packaging materials

        Args:
            wholesale_price: Per-unit cost from supplier.
            delivery_loc: Supplier shipping origin (province).
            category: Product category for commission lookup.
            sell_price: Expected selling price (for commission calculation).

        Returns:
            LandedCostBreakdown with itemized costs and margin estimate.
        """
        # Determine shipping cost by region
        shipping_cost = SHIPPING_COST_BY_REGION.get("default", 5.0)
        for region, cost in SHIPPING_COST_BY_REGION.items():
            if region != "default" and region in delivery_loc:
                shipping_cost = cost
                break

        # Determine commission rate by category
        commission_rate = COMMISSION_RATES.get("default", 0.05)
        for cat_key, rate in COMMISSION_RATES.items():
            if cat_key != "default" and cat_key in category:
                commission_rate = rate
                break

        # Determine packaging cost
        packaging_cost = PACKAGING_COST.get("default", 2.0)
        for cat_key, cost in PACKAGING_COST.items():
            if cat_key != "default" and cat_key in category:
                packaging_cost = cost
                break

        # Commission is on sell price (or estimated sell price)
        effective_sell_price = sell_price if sell_price > 0 else wholesale_price * 3.0
        commission_amount = effective_sell_price * commission_rate

        total_landed_cost = wholesale_price + shipping_cost + commission_amount + packaging_cost

        # Margin calculation
        gross_margin = effective_sell_price - total_landed_cost
        margin_percentage = (
            (gross_margin / effective_sell_price * 100.0)
            if effective_sell_price > 0
            else 0.0
        )

        return LandedCostBreakdown(
            wholesale_price=round(wholesale_price, 2),
            shipping_cost=round(shipping_cost, 2),
            commission_rate=commission_rate,
            commission_amount=round(commission_amount, 2),
            packaging_cost=round(packaging_cost, 2),
            total_landed_cost=round(total_landed_cost, 2),
            sell_price=round(effective_sell_price, 2),
            gross_margin=round(gross_margin, 2),
            margin_percentage=round(margin_percentage, 2),
        )

    def _parse_search_results(self, data: dict[str, Any]) -> list[SupplierResult]:
        """Parse 1688 API response into SupplierResult objects."""
        results: list[SupplierResult] = []

        product_list = data.get("data", {}).get("products", [])
        if not product_list:
            # Try alternative response format
            product_list = data.get("result", {}).get("products", [])

        for item in product_list:
            try:
                result = SupplierResult(
                    supplier_name=item.get("supplierName", ""),
                    supplier_id=str(item.get("supplierId", "")),
                    product_title=item.get("subject", item.get("title", "")),
                    product_url=item.get("productUrl", item.get("detailUrl", "")),
                    wholesale_price=float(item.get("priceInfo", {}).get("price", 0)),
                    moq=int(item.get("moq", item.get("minOrderQuantity", 1))),
                    supplier_rating=float(item.get("supplierScore", 0)),
                    transaction_count=int(item.get("bookedCount", item.get("transactionCount", 0))),
                    delivery_location=item.get("location", item.get("province", "")),
                    image_url=item.get("imageUrl", item.get("mainImage", "")),
                    sample_available=item.get("sampleAvailable", False),
                )
                results.append(result)
            except (ValueError, TypeError, KeyError) as e:
                logger.warning("Failed to parse 1688 result item: %s", str(e))
                continue

        return results
