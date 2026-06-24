"""Product Discovery Service - orchestrates the daily scanning pipeline.

Coordinates: trending product fetching, scoring, 1688 supplier matching,
margin calculation, and shortlist generation.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded
from app.core.rate_limiter import TokenBucketRateLimiter
from app.models.discovery import (
    OperatorDecision,
    ProductBrief,
    SourceCandidate,
    SourceCandidateStatus,
    TrendingProduct,
    TrendingSource,
)

from .scoring import TrendScorer
from .suppliers import LandedCostBreakdown, SupplierMatcher, SupplierResult

logger = logging.getLogger(__name__)


# -- Data transfer objects ---------------------------------------------------


@dataclass(slots=True)
class SearchTrend:
    """A rising search keyword from trend data platforms."""

    keyword: str
    search_volume: int
    growth_rate: float  # percentage growth over period
    category: str
    source: str  # "feigua" or "douyin_hot"


@dataclass(slots=True)
class ScoredCandidate:
    """A product candidate with its computed opportunity score."""

    product: TrendingProduct
    score: float
    rank: int


@dataclass(slots=True)
class MarginEstimate:
    """Full margin calculation result."""

    sell_price: float
    wholesale_price: float
    landed_cost: float
    gross_margin: float
    margin_percentage: float
    breakdown: LandedCostBreakdown


@dataclass(slots=True)
class ProductBriefData:
    """LLM-generated product analysis brief."""

    market_analysis: str
    sourcing_summary: str
    margin_estimate: float
    recommended_action: str


@dataclass(slots=True)
class ScanResult:
    """Result of a full daily scan pipeline run."""

    scan_id: str
    scan_date: date
    products_fetched: int
    candidates_scored: int
    suppliers_matched: int
    shortlist_count: int
    avg_margin: float
    top_candidates: list[ScoredCandidate]


class DiscoveryService:
    """Orchestrates the product discovery and sourcing pipeline.

    Pipeline stages:
        1. Fetch trending products from 蝉妈妈 (Chanmama)
        2. Fetch rising search trends from 飞瓜/抖音热榜
        3. Score candidates by demand/competition factors
        4. Match top candidates against 1688 suppliers
        5. Calculate landed costs and margins
        6. Generate LLM-powered product briefs
        7. Present ranked shortlist to operators
    """

    def __init__(
        self,
        db: AsyncSession,
        rate_limiter: TokenBucketRateLimiter,
    ) -> None:
        self.db = db
        self.rate_limiter = rate_limiter
        self.scorer = TrendScorer()
        self.supplier_matcher = SupplierMatcher(rate_limiter)
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._http_client

    async def close(self) -> None:
        """Clean up resources."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        await self.supplier_matcher.close()

    # -------------------------------------------------------------------------
    # Main pipeline
    # -------------------------------------------------------------------------

    async def run_daily_scan(self) -> ScanResult:
        """Execute the full daily discovery pipeline.

        Steps:
            1. Fetch trending products
            2. Score all candidates
            3. Match top candidates with 1688 suppliers
            4. Calculate margins
            5. Generate shortlist

        Returns:
            ScanResult with summary statistics and top candidates.
        """
        scan_id = str(uuid.uuid4())
        scan_date = date.today()

        logger.info("Starting daily scan: scan_id=%s, date=%s", scan_id, scan_date)

        # Stage 1: Fetch trending products
        trending = await self.fetch_trending_products(limit=500)
        logger.info("Fetched %d trending products", len(trending))

        # Stage 2: Score candidates
        scored = self.score_candidates(trending)
        logger.info("Scored %d candidates", len(scored))

        # Stage 3: Take top candidates for supplier matching
        top_n = min(50, len(scored))
        top_candidates = scored[:top_n]

        # Stage 4: Match with 1688 suppliers
        suppliers_matched = 0
        for candidate in top_candidates:
            try:
                suppliers = await self.search_1688_suppliers(candidate.product)
                if suppliers:
                    suppliers_matched += 1
                    # Save best supplier as SourceCandidate
                    await self._save_source_candidates(candidate.product, suppliers)
            except RateLimitExceeded:
                logger.warning(
                    "Rate limit hit during supplier matching, stopping at %d",
                    suppliers_matched,
                )
                break
            except Exception as e:
                logger.error(
                    "Error matching suppliers for %s: %s",
                    candidate.product.name,
                    str(e),
                )

        # Stage 5: Calculate average margin for shortlist
        avg_margin = await self._calculate_avg_margin(top_candidates)

        # Persist scan metadata
        await self.db.flush()

        result = ScanResult(
            scan_id=scan_id,
            scan_date=scan_date,
            products_fetched=len(trending),
            candidates_scored=len(scored),
            suppliers_matched=suppliers_matched,
            shortlist_count=top_n,
            avg_margin=avg_margin,
            top_candidates=top_candidates[:20],
        )

        logger.info(
            "Daily scan complete: scan_id=%s, fetched=%d, scored=%d, matched=%d, avg_margin=%.1f%%",
            scan_id,
            result.products_fetched,
            result.candidates_scored,
            result.suppliers_matched,
            result.avg_margin,
        )

        return result

    # -------------------------------------------------------------------------
    # Data fetching
    # -------------------------------------------------------------------------

    async def fetch_trending_products(self, limit: int = 500) -> list[TrendingProduct]:
        """Fetch trending products from 蝉妈妈 API, sorted by 7-day GMV growth.

        Args:
            limit: Maximum number of products to fetch.

        Returns:
            List of TrendingProduct instances (not yet persisted).
        """
        await self.rate_limiter.acquire("chanmama")

        client = await self._get_client()
        products: list[TrendingProduct] = []
        page_size = min(limit, 50)
        pages_needed = (limit + page_size - 1) // page_size

        for page in range(1, pages_needed + 1):
            try:
                await self.rate_limiter.acquire("chanmama")
            except RateLimitExceeded:
                logger.warning("Chanmama rate limit reached at page %d", page)
                break

            logger.info(
                "Fetching Chanmama trending page %d/%d",
                page,
                pages_needed,
                extra={"api_cost": "chanmama_trending", "tokens_used": 1},
            )

            try:
                response = await client.get(
                    "https://api.chanmama.com/v2/douyin/product/trending",
                    params={
                        "page": page,
                        "page_size": page_size,
                        "sort_by": "gmv_growth_7d",
                        "sort_order": "desc",
                    },
                    headers={
                        "Authorization": f"Bearer {settings.CHANMAMA_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Chanmama API error: status=%d", e.response.status_code)
                break
            except httpx.RequestError as e:
                logger.error("Chanmama network error: %s", str(e))
                break

            items = data.get("data", {}).get("list", [])
            if not items:
                break

            for item in items:
                product = TrendingProduct(
                    external_id=str(item.get("product_id", "")),
                    name=item.get("title", ""),
                    category=item.get("category", "未分类"),
                    source=TrendingSource.CHANMAMA,
                    sales_volume_7d=int(item.get("sales_7d", 0)),
                    growth_rate_7d=float(item.get("gmv_growth_7d", 0.0)),
                    competition_count=int(item.get("shop_count", 0)),
                    avg_competitor_rating=float(item.get("avg_rating", 0.0)),
                    search_volume=int(item.get("search_volume", 0)),
                    scanned_at=datetime.now(timezone.utc),
                )
                products.append(product)

            if len(products) >= limit:
                break

        # Sort by 7-day GMV growth descending
        products.sort(key=lambda p: p.growth_rate_7d, reverse=True)
        return products[:limit]

    async def fetch_search_trends(self, limit: int = 100) -> list[SearchTrend]:
        """Fetch rising search keywords from 飞瓜/抖音热榜.

        Args:
            limit: Maximum number of search trends to return.

        Returns:
            List of SearchTrend objects sorted by growth rate.
        """
        await self.rate_limiter.acquire("feigua")

        client = await self._get_client()
        trends: list[SearchTrend] = []

        logger.info(
            "Fetching search trends from Feigua",
            extra={"api_cost": "feigua_search_trends", "tokens_used": 1},
        )

        try:
            response = await client.get(
                "https://api.feigua.cn/v1/douyin/search/trending",
                params={
                    "limit": limit,
                    "sort_by": "growth_rate",
                    "period": "7d",
                },
                headers={
                    "Authorization": f"Bearer {settings.FEIGUA_API_KEY}",
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Feigua API error: status=%d", e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("Feigua network error: %s", str(e))
            return []

        for item in data.get("data", {}).get("keywords", []):
            trend = SearchTrend(
                keyword=item.get("keyword", ""),
                search_volume=int(item.get("search_volume", 0)),
                growth_rate=float(item.get("growth_rate", 0.0)),
                category=item.get("category", ""),
                source="feigua",
            )
            trends.append(trend)

        trends.sort(key=lambda t: t.growth_rate, reverse=True)
        return trends[:limit]

    # -------------------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------------------

    def score_candidates(self, products: list[TrendingProduct]) -> list[ScoredCandidate]:
        """Score and rank a list of trending products.

        Uses batch percentile normalization across all products
        for fair comparison.

        Args:
            products: List of TrendingProduct instances to score.

        Returns:
            List of ScoredCandidate sorted by score descending.
        """
        scored_pairs = self.scorer.calculate_score_batch(products)

        candidates = [
            ScoredCandidate(product=product, score=score, rank=rank + 1)
            for rank, (product, score) in enumerate(scored_pairs)
        ]

        # Persist scores to the product objects
        for candidate in candidates:
            candidate.product.score = candidate.score

        return candidates

    # -------------------------------------------------------------------------
    # Supplier matching
    # -------------------------------------------------------------------------

    async def search_1688_suppliers(self, product: TrendingProduct) -> list[SupplierResult]:
        """Search 1688 for suppliers matching a product candidate.

        Searches by keyword derived from product name. Filters results
        by quality thresholds.

        Args:
            product: The product to find suppliers for.

        Returns:
            Filtered and ranked list of SupplierResult.
        """
        # Extract keywords from product name (first 20 chars or key terms)
        keyword = product.name[:30].strip()

        raw_results = await self.supplier_matcher.search_by_keyword(keyword)

        # Filter by quality thresholds
        filtered = self.supplier_matcher.filter_suppliers(
            raw_results,
            min_rating=4.5,
            min_transactions=1000,
        )

        return filtered

    # -------------------------------------------------------------------------
    # Margin calculation
    # -------------------------------------------------------------------------

    def calculate_margin(
        self,
        sell_price: float,
        wholesale_price: float,
        category: str,
    ) -> MarginEstimate:
        """Calculate full landed cost and margin estimate.

        Accounts for: wholesale cost, shipping, platform commission,
        and packaging materials.

        Args:
            sell_price: Expected selling price on Douyin.
            wholesale_price: Unit cost from 1688 supplier.
            category: Product category (for commission/packaging lookup).

        Returns:
            MarginEstimate with full breakdown.
        """
        breakdown = SupplierMatcher.calculate_landed_cost(
            wholesale_price=wholesale_price,
            delivery_loc="浙江",  # Default to most common origin
            category=category,
            sell_price=sell_price,
        )

        return MarginEstimate(
            sell_price=sell_price,
            wholesale_price=wholesale_price,
            landed_cost=breakdown.total_landed_cost,
            gross_margin=breakdown.gross_margin,
            margin_percentage=breakdown.margin_percentage,
            breakdown=breakdown,
        )

    # -------------------------------------------------------------------------
    # Brief generation (LLM-powered)
    # -------------------------------------------------------------------------

    async def generate_product_brief(self, candidate: ScoredCandidate) -> ProductBriefData:
        """Generate an LLM-powered product analysis brief.

        Calls the AI service to produce market analysis, sourcing summary,
        and recommended action for a candidate product.

        Args:
            candidate: The scored candidate to analyze.

        Returns:
            ProductBriefData with LLM-generated content.
        """
        await self.rate_limiter.acquire("ai_service")

        client = await self._get_client()
        product = candidate.product

        prompt = (
            f"分析以下抖音热门商品的市场机会:\n\n"
            f"商品名称: {product.name}\n"
            f"类目: {product.category}\n"
            f"7天销量: {product.sales_volume_7d}\n"
            f"7天增长率: {product.growth_rate_7d:.1f}%\n"
            f"竞争店铺数: {product.competition_count}\n"
            f"竞品平均评分: {product.avg_competitor_rating:.1f}\n"
            f"搜索量: {product.search_volume}\n"
            f"综合得分: {candidate.score:.1f}/100\n\n"
            f"请提供:\n"
            f"1. 市场分析 (200字以内)\n"
            f"2. 采购建议摘要 (100字以内)\n"
            f"3. 预估利润率\n"
            f"4. 建议操作 (上架/观望/放弃)"
        )

        logger.info(
            "Generating product brief for: %s",
            product.name[:50],
            extra={"api_cost": "ai_brief_generation", "tokens_used": 1},
        )

        try:
            response = await client.post(
                f"{settings.AI_API_BASE_URL}/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是一位资深电商选品分析师，专注抖音电商。"
                                "请用简洁专业的中文回答。"
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800,
                },
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            ai_data = response.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("AI service error for brief generation: %s", str(e))
            return ProductBriefData(
                market_analysis="AI分析服务暂时不可用",
                sourcing_summary="请人工评估",
                margin_estimate=0.0,
                recommended_action="观望",
            )

        content = ai_data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse structured response
        brief = self._parse_ai_brief(content, candidate)
        return brief

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _save_source_candidates(
        self,
        product: TrendingProduct,
        suppliers: list[SupplierResult],
    ) -> None:
        """Persist top supplier matches as SourceCandidate records."""
        # Ensure product is persisted
        if product.id is None:
            self.db.add(product)
            await self.db.flush()

        for supplier in suppliers[:5]:  # Keep top 5 per product
            # Calculate landed cost
            breakdown = SupplierMatcher.calculate_landed_cost(
                wholesale_price=supplier.wholesale_price,
                delivery_loc=supplier.delivery_location,
                category=product.category,
            )

            source_candidate = SourceCandidate(
                trending_product_id=product.id,
                supplier_name=supplier.supplier_name,
                supplier_url=supplier.product_url,
                wholesale_price=supplier.wholesale_price,
                moq=supplier.moq,
                supplier_rating=supplier.supplier_rating,
                delivery_location=supplier.delivery_location,
                sample_available=supplier.sample_available,
                estimated_landed_cost=breakdown.total_landed_cost,
                estimated_margin=breakdown.margin_percentage,
                status=SourceCandidateStatus.IDENTIFIED,
            )
            self.db.add(source_candidate)

    async def _calculate_avg_margin(self, candidates: list[ScoredCandidate]) -> float:
        """Calculate average estimated margin across shortlisted candidates."""
        if not candidates:
            return 0.0

        # Query existing source candidates for these products
        product_ids = [
            c.product.id for c in candidates if c.product.id is not None
        ]

        if not product_ids:
            return 0.0

        stmt = select(func.avg(SourceCandidate.estimated_margin)).where(
            SourceCandidate.trending_product_id.in_(product_ids)
        )
        result = await self.db.execute(stmt)
        avg = result.scalar()

        return float(avg) if avg else 0.0

    def _parse_ai_brief(self, content: str, candidate: ScoredCandidate) -> ProductBriefData:
        """Parse AI response into structured ProductBriefData."""
        lines = content.strip().split("\n")

        market_analysis = ""
        sourcing_summary = ""
        recommended_action = "观望"
        margin_estimate = 0.0

        # Simple section-based parsing
        current_section = ""
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if "市场分析" in line_stripped or "1." in line_stripped[:3]:
                current_section = "market"
                line_stripped = line_stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
                if line_stripped:
                    market_analysis = line_stripped
            elif "采购建议" in line_stripped or "2." in line_stripped[:3]:
                current_section = "sourcing"
                line_stripped = line_stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
                if line_stripped:
                    sourcing_summary = line_stripped
            elif "利润率" in line_stripped or "3." in line_stripped[:3]:
                current_section = "margin"
                # Extract percentage
                import re

                match = re.search(r"(\d+\.?\d*)\s*%", line_stripped)
                if match:
                    margin_estimate = float(match.group(1))
            elif "建议" in line_stripped and "操作" in line_stripped or "4." in line_stripped[:3]:
                current_section = "action"
                for action in ["上架", "观望", "放弃"]:
                    if action in line_stripped:
                        recommended_action = action
                        break
            else:
                # Append to current section
                if current_section == "market":
                    market_analysis += " " + line_stripped
                elif current_section == "sourcing":
                    sourcing_summary += " " + line_stripped

        return ProductBriefData(
            market_analysis=market_analysis.strip() or "暂无分析",
            sourcing_summary=sourcing_summary.strip() or "暂无建议",
            margin_estimate=margin_estimate,
            recommended_action=recommended_action,
        )
