"""Celery tasks for product discovery pipeline.

Scheduled and on-demand tasks that drive the daily scanning,
scoring, supplier matching, and brief generation workflows.
"""

import logging
from datetime import date, datetime, timezone

from celery import chain, chord, group
from celery.schedules import crontab
from sqlalchemy import select, update

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


# -- Schedule registration ---------------------------------------------------

celery_app.conf.beat_schedule = {
    **getattr(celery_app.conf, "beat_schedule", {}),
    "discovery-daily-scan": {
        "task": "app.modules.discovery.tasks.daily_scan_task",
        "schedule": crontab(hour=6, minute=0),  # 06:00 daily (Asia/Shanghai)
        "options": {"queue": "discovery"},
    },
    "discovery-price-monitor": {
        "task": "app.modules.discovery.tasks.price_monitor_task",
        "schedule": crontab(hour=8, minute=0),  # 08:00 daily
        "options": {"queue": "discovery"},
    },
}


# -- Tasks -------------------------------------------------------------------


@celery_app.task(
    name="app.modules.discovery.tasks.daily_scan_task",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="discovery",
)
def daily_scan_task(self) -> dict:
    """Execute the full daily product discovery scan.

    Scheduled at 06:00 daily. Fetches trends, scores products,
    triggers supplier matching for top candidates, and generates briefs.

    Returns:
        Summary dict with scan statistics.
    """
    import asyncio

    from app.core.database import async_session_factory
    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.modules.discovery.service import DiscoveryService

    async def _run() -> dict:
        redis = await get_redis()
        rate_limiter = TokenBucketRateLimiter(redis=redis)

        async with async_session_factory() as db:
            service = DiscoveryService(db=db, rate_limiter=rate_limiter)
            try:
                result = await service.run_daily_scan()
                await db.commit()

                # Trigger downstream tasks for top candidates
                top_ids = [
                    str(c.product.id)
                    for c in result.top_candidates
                    if c.product.id is not None
                ]

                if top_ids:
                    # Trigger supplier matching in parallel
                    supplier_tasks = group(
                        match_suppliers_task.s(cid) for cid in top_ids[:30]
                    )
                    supplier_tasks.apply_async(queue="discovery")

                return {
                    "scan_id": result.scan_id,
                    "scan_date": str(result.scan_date),
                    "products_fetched": result.products_fetched,
                    "candidates_scored": result.candidates_scored,
                    "suppliers_matched": result.suppliers_matched,
                    "shortlist_count": result.shortlist_count,
                    "avg_margin": result.avg_margin,
                }
            except Exception as e:
                logger.error("Daily scan failed: %s", str(e), exc_info=True)
                raise self.retry(exc=e)
            finally:
                await service.close()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(
    name="app.modules.discovery.tasks.score_candidates_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="discovery",
)
def score_candidates_task(self, scan_id: str) -> dict:
    """Score all candidates for a given scan batch.

    Args:
        scan_id: UUID of the scan to process.

    Returns:
        Dict with scoring statistics.
    """
    import asyncio

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.discovery import TrendingProduct
    from app.modules.discovery.scoring import TrendScorer

    async def _run() -> dict:
        async with async_session_factory() as db:
            # Fetch unscored products from today's scan
            stmt = select(TrendingProduct).where(
                TrendingProduct.score == 0.0,
            ).limit(500)
            result = await db.execute(stmt)
            products = list(result.scalars().all())

            if not products:
                return {"scan_id": scan_id, "scored": 0}

            scorer = TrendScorer()
            scored_pairs = scorer.calculate_score_batch(products)

            # Update scores in DB
            for product, score in scored_pairs:
                product.score = score

            await db.commit()

            return {
                "scan_id": scan_id,
                "scored": len(scored_pairs),
                "top_score": scored_pairs[0][1] if scored_pairs else 0,
                "avg_score": sum(s for _, s in scored_pairs) / len(scored_pairs),
            }

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(
    name="app.modules.discovery.tasks.match_suppliers_task",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue="discovery",
)
def match_suppliers_task(self, candidate_id: str) -> dict:
    """Find 1688 suppliers for a specific candidate product.

    Args:
        candidate_id: UUID of the TrendingProduct to match.

    Returns:
        Dict with matching results summary.
    """
    import asyncio
    import uuid

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.models.discovery import (
        SourceCandidate,
        SourceCandidateStatus,
        TrendingProduct,
    )
    from app.modules.discovery.suppliers import SupplierMatcher

    async def _run() -> dict:
        redis = await get_redis()
        rate_limiter = TokenBucketRateLimiter(redis=redis)
        matcher = SupplierMatcher(rate_limiter)

        try:
            async with async_session_factory() as db:
                # Fetch the product
                stmt = select(TrendingProduct).where(
                    TrendingProduct.id == uuid.UUID(candidate_id)
                )
                result = await db.execute(stmt)
                product = result.scalar_one_or_none()

                if product is None:
                    return {"candidate_id": candidate_id, "status": "not_found"}

                # Search by keyword
                keyword = product.name[:30].strip()
                raw_results = await matcher.search_by_keyword(keyword)
                filtered = matcher.filter_suppliers(raw_results)

                # Save results
                saved_count = 0
                for supplier in filtered[:5]:
                    breakdown = SupplierMatcher.calculate_landed_cost(
                        wholesale_price=supplier.wholesale_price,
                        delivery_loc=supplier.delivery_location,
                        category=product.category,
                    )

                    sc = SourceCandidate(
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
                    db.add(sc)
                    saved_count += 1

                await db.commit()

                return {
                    "candidate_id": candidate_id,
                    "product_name": product.name,
                    "raw_results": len(raw_results),
                    "filtered_results": len(filtered),
                    "saved": saved_count,
                }
        finally:
            await matcher.close()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(
    name="app.modules.discovery.tasks.generate_briefs_task",
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    queue="discovery",
)
def generate_briefs_task(self, shortlist_ids: list[str]) -> dict:
    """Generate LLM-powered product briefs for top candidates.

    Args:
        shortlist_ids: List of TrendingProduct UUIDs to generate briefs for.

    Returns:
        Summary of brief generation results.
    """
    import asyncio
    import uuid

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.models.discovery import ProductBrief, TrendingProduct
    from app.modules.discovery.service import DiscoveryService, ScoredCandidate

    async def _run() -> dict:
        redis = await get_redis()
        rate_limiter = TokenBucketRateLimiter(redis=redis)

        async with async_session_factory() as db:
            service = DiscoveryService(db=db, rate_limiter=rate_limiter)
            generated = 0
            errors = 0

            try:
                for product_id_str in shortlist_ids:
                    stmt = select(TrendingProduct).where(
                        TrendingProduct.id == uuid.UUID(product_id_str)
                    )
                    result = await db.execute(stmt)
                    product = result.scalar_one_or_none()

                    if product is None:
                        continue

                    candidate = ScoredCandidate(
                        product=product,
                        score=product.score,
                        rank=0,
                    )

                    try:
                        brief_data = await service.generate_product_brief(candidate)

                        brief = ProductBrief(
                            trending_product_id=product.id,
                            market_analysis=brief_data.market_analysis,
                            sourcing_summary=brief_data.sourcing_summary,
                            margin_estimate=brief_data.margin_estimate,
                            recommended_action=brief_data.recommended_action,
                        )
                        db.add(brief)
                        generated += 1

                    except Exception as e:
                        logger.error(
                            "Brief generation failed for %s: %s",
                            product.name,
                            str(e),
                        )
                        errors += 1

                await db.commit()
            finally:
                await service.close()

            return {
                "requested": len(shortlist_ids),
                "generated": generated,
                "errors": errors,
            }

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(
    name="app.modules.discovery.tasks.price_monitor_task",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="discovery",
)
def price_monitor_task(self) -> dict:
    """Daily competitor price monitoring.

    Tracks price changes for products in the active shortlist
    to detect pricing opportunities or threats.

    Returns:
        Summary of price monitoring results.
    """
    import asyncio
    import uuid

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.rate_limiter import TokenBucketRateLimiter
    from app.core.redis import get_redis
    from app.models.discovery import (
        OperatorDecision,
        ProductBrief,
        SourceCandidate,
        SourceCandidateStatus,
        TrendingProduct,
    )
    from app.modules.discovery.suppliers import SupplierMatcher

    async def _run() -> dict:
        redis = await get_redis()
        rate_limiter = TokenBucketRateLimiter(redis=redis)
        matcher = SupplierMatcher(rate_limiter)

        try:
            async with async_session_factory() as db:
                # Get active/approved candidates
                stmt = (
                    select(SourceCandidate)
                    .where(
                        SourceCandidate.status.in_([
                            SourceCandidateStatus.APPROVED,
                            SourceCandidateStatus.SAMPLED,
                        ])
                    )
                    .limit(100)
                )
                result = await db.execute(stmt)
                candidates = list(result.scalars().all())

                if not candidates:
                    return {"monitored": 0, "price_changes": 0}

                price_changes = 0
                for candidate in candidates:
                    try:
                        # Re-check supplier pricing
                        results = await matcher.search_by_keyword(
                            candidate.supplier_name[:20]
                        )
                        if results:
                            new_price = results[0].wholesale_price
                            if abs(new_price - float(candidate.wholesale_price)) > 0.5:
                                candidate.wholesale_price = new_price
                                # Recalculate margin
                                breakdown = SupplierMatcher.calculate_landed_cost(
                                    wholesale_price=new_price,
                                    delivery_loc=candidate.delivery_location,
                                    category="default",
                                )
                                candidate.estimated_landed_cost = breakdown.total_landed_cost
                                candidate.estimated_margin = breakdown.margin_percentage
                                price_changes += 1

                    except RateLimitExceeded:
                        logger.warning("Rate limit during price monitoring")
                        break
                    except Exception as e:
                        logger.error("Price monitor error: %s", str(e))

                await db.commit()

                return {
                    "monitored": len(candidates),
                    "price_changes": price_changes,
                }
        finally:
            await matcher.close()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
