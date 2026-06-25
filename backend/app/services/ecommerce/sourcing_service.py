"""Sourcing service - multi-provider sourcing aggregation with concurrent requests."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.integrations.base import BaseSourcingProvider
from app.integrations.registry import ProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class SourcingQuery:
    """Query parameters for sourcing search."""

    keyword: str
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_order_quantity: Optional[int] = None
    origin_country: Optional[str] = None
    sort_by: str = "relevance"
    page: int = 1
    page_size: int = 20


@dataclass
class NormalizedProduct:
    """Normalized product from any sourcing provider."""

    provider: str
    external_id: str
    title: str
    description: str = ""
    price: float = 0.0
    currency: str = "CNY"
    min_order_quantity: int = 1
    images: list[str] = field(default_factory=list)
    supplier_name: str = ""
    supplier_rating: Optional[float] = None
    url: str = ""
    shipping_info: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourcingResult:
    """Aggregated result from multiple sourcing providers."""

    products: list[NormalizedProduct]
    total_count: int
    providers_queried: list[str]
    providers_failed: list[str]
    query_time_ms: float


class SourcingService:
    """Multi-provider sourcing aggregation service.

    Executes concurrent requests to multiple sourcing providers,
    normalizes results, and returns a merged, deduplicated list.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        timeout_seconds: float = 30.0,
        max_concurrent: int = 5,
    ):
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.max_concurrent = max_concurrent

    async def search(
        self,
        query: SourcingQuery,
        *,
        providers: Optional[list[str]] = None,
    ) -> SourcingResult:
        """Search products across multiple sourcing providers concurrently.

        Args:
            query: Search parameters.
            providers: Optional list of provider names. If None, uses all enabled.

        Returns:
            Aggregated and normalized results from all providers.
        """
        import time

        start_time = time.monotonic()

        # Get target providers
        if providers:
            sourcing_providers: list[BaseSourcingProvider] = [
                self.registry.get("sourcing", name)
                for name in providers
                if self.registry.get("sourcing", name) is not None
            ]
        else:
            sourcing_providers = self.registry.get_enabled("sourcing")

        if not sourcing_providers:
            return SourcingResult(
                products=[],
                total_count=0,
                providers_queried=[],
                providers_failed=[],
                query_time_ms=0.0,
            )

        # Execute concurrent requests with semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.max_concurrent)
        tasks = [
            self._query_provider(provider, query, semaphore)
            for provider in sourcing_providers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        all_products: list[NormalizedProduct] = []
        providers_queried: list[str] = []
        providers_failed: list[str] = []

        for provider, result in zip(sourcing_providers, results):
            provider_name = provider.provider_name
            if isinstance(result, Exception):
                logger.error(
                    f"Provider {provider_name} failed: {result}",
                    exc_info=result,
                )
                providers_failed.append(provider_name)
            else:
                providers_queried.append(provider_name)
                all_products.extend(result)

        # Merge and deduplicate
        merged = self._merge_and_deduplicate(all_products)

        # Apply sorting
        merged = self._sort_products(merged, query.sort_by)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return SourcingResult(
            products=merged,
            total_count=len(merged),
            providers_queried=providers_queried,
            providers_failed=providers_failed,
            query_time_ms=round(elapsed_ms, 2),
        )

    async def _query_provider(
        self,
        provider: BaseSourcingProvider,
        query: SourcingQuery,
        semaphore: asyncio.Semaphore,
    ) -> list[NormalizedProduct]:
        """Query a single provider with timeout and semaphore control."""
        async with semaphore:
            try:
                raw_results = await asyncio.wait_for(
                    provider.search_products(
                        keyword=query.keyword,
                        category=query.category,
                        min_price=query.min_price,
                        max_price=query.max_price,
                        page=query.page,
                        page_size=query.page_size,
                    ),
                    timeout=self.timeout_seconds,
                )
                return self._normalize_results(provider.provider_name, raw_results)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Provider {provider.provider_name} timed out "
                    f"after {self.timeout_seconds}s"
                )
                raise
            except Exception as e:
                logger.error(f"Provider {provider.provider_name} error: {e}")
                raise

    def _normalize_results(
        self, provider_name: str, raw_results: list[dict[str, Any]]
    ) -> list[NormalizedProduct]:
        """Normalize raw provider results to common schema."""
        normalized = []
        for item in raw_results:
            product = NormalizedProduct(
                provider=provider_name,
                external_id=str(item.get("id", "")),
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=float(item.get("price", 0)),
                currency=item.get("currency", "CNY"),
                min_order_quantity=int(item.get("min_order_quantity", 1)),
                images=item.get("images", []),
                supplier_name=item.get("supplier_name", ""),
                supplier_rating=item.get("supplier_rating"),
                url=item.get("url", ""),
                shipping_info=item.get("shipping_info", {}),
                attributes=item.get("attributes", {}),
                raw_data=item,
            )
            normalized.append(product)
        return normalized

    def _merge_and_deduplicate(
        self, products: list[NormalizedProduct]
    ) -> list[NormalizedProduct]:
        """Merge products from multiple providers and remove duplicates.

        Deduplication is based on title similarity and price proximity.
        """
        seen: dict[str, NormalizedProduct] = {}
        result: list[NormalizedProduct] = []

        for product in products:
            # Simple dedup key: normalized title + price bucket
            dedup_key = self._generate_dedup_key(product)
            if dedup_key not in seen:
                seen[dedup_key] = product
                result.append(product)
            else:
                # Keep the one with better supplier rating
                existing = seen[dedup_key]
                if (product.supplier_rating or 0) > (existing.supplier_rating or 0):
                    result.remove(existing)
                    seen[dedup_key] = product
                    result.append(product)

        return result

    @staticmethod
    def _generate_dedup_key(product: NormalizedProduct) -> str:
        """Generate a deduplication key for a product."""
        # Normalize title: lowercase, strip whitespace
        title_normalized = product.title.lower().strip()[:50]
        # Price bucket: round to nearest integer
        price_bucket = round(product.price)
        return f"{title_normalized}:{price_bucket}"

    @staticmethod
    def _sort_products(
        products: list[NormalizedProduct], sort_by: str
    ) -> list[NormalizedProduct]:
        """Sort products by the given criteria."""
        if sort_by == "price_asc":
            return sorted(products, key=lambda p: p.price)
        elif sort_by == "price_desc":
            return sorted(products, key=lambda p: p.price, reverse=True)
        elif sort_by == "rating":
            return sorted(
                products,
                key=lambda p: p.supplier_rating or 0,
                reverse=True,
            )
        # Default: relevance (maintain original order)
        return products

    async def get_product_detail(
        self, provider_name: str, external_id: str
    ) -> Optional[dict[str, Any]]:
        """Get detailed product information from a specific provider.

        Args:
            provider_name: Name of the sourcing provider.
            external_id: External product ID in that provider.

        Returns:
            Product detail dictionary or None.
        """
        provider: Optional[BaseSourcingProvider] = self.registry.get(
            "sourcing", provider_name
        )
        if provider is None:
            return None

        try:
            return await asyncio.wait_for(
                provider.get_product_detail(external_id),
                timeout=self.timeout_seconds,
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(
                f"Failed to get detail from {provider_name}: {e}"
            )
            return None
