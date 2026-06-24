"""FastAPI router for the Product Discovery & Sourcing module.

Exposes endpoints for trending products, shortlists, product briefs,
operator approval/rejection, manual scan triggers, and stats.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.rate_limiter import TokenBucketRateLimiter
from app.core.redis import get_redis
from app.models.discovery import (
    OperatorDecision,
    ProductBrief,
    SourceCandidate,
    SourceCandidateStatus,
    TrendingProduct,
    TrendingSource,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


# -- Response schemas --------------------------------------------------------


class TrendingProductResponse(BaseModel):
    id: str
    external_id: str
    name: str
    category: str
    source: str
    sales_volume_7d: int
    growth_rate_7d: float
    competition_count: int
    avg_competitor_rating: float
    search_volume: int
    score: float
    scanned_at: datetime

    class Config:
        from_attributes = True


class SupplierInfo(BaseModel):
    supplier_name: str
    wholesale_price: float
    moq: int
    supplier_rating: float
    delivery_location: str
    estimated_landed_cost: float
    estimated_margin: float
    status: str


class ShortlistItemResponse(BaseModel):
    id: str
    name: str
    category: str
    score: float
    growth_rate_7d: float
    sales_volume_7d: int
    competition_count: int
    best_margin: float | None = None
    best_wholesale_price: float | None = None
    supplier_count: int = 0
    scanned_at: datetime


class ProductBriefResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    category: str
    score: float
    market_analysis: str
    sourcing_summary: str
    margin_estimate: float
    recommended_action: str
    operator_decision: str
    suppliers: list[SupplierInfo] = []
    scanned_at: datetime


class StatsResponse(BaseModel):
    total_candidates: int
    approved_count: int
    rejected_count: int
    pending_count: int
    avg_margin: float
    top_categories: list[dict[str, Any]]
    scans_today: int


class ScanTriggerResponse(BaseModel):
    task_id: str
    status: str
    message: str


class DecisionRequest(BaseModel):
    reason: str = Field(default="", max_length=500, description="Reason for decision")


# -- Dependency helpers ------------------------------------------------------


async def get_rate_limiter(redis: Redis = Depends(get_redis)) -> TokenBucketRateLimiter:
    return TokenBucketRateLimiter(redis=redis)


# -- Endpoints ---------------------------------------------------------------


@router.get("/trending", response_model=list[TrendingProductResponse])
async def get_trending_products(
    limit: int = Query(default=50, ge=1, le=200),
    category: str | None = Query(default=None),
    source: str | None = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0),
    db: AsyncSession = Depends(get_db),
) -> list[TrendingProductResponse]:
    """Get current trending products sorted by score.

    Returns the latest scanned trending products with optional
    filtering by category, source, and minimum score.
    """
    stmt = select(TrendingProduct).order_by(TrendingProduct.score.desc())

    if category:
        stmt = stmt.where(TrendingProduct.category.ilike(f"%{category}%"))
    if source:
        stmt = stmt.where(TrendingProduct.source == source)
    if min_score > 0:
        stmt = stmt.where(TrendingProduct.score >= min_score)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()

    return [
        TrendingProductResponse(
            id=str(p.id),
            external_id=p.external_id,
            name=p.name,
            category=p.category,
            source=p.source.value if isinstance(p.source, TrendingSource) else p.source,
            sales_volume_7d=p.sales_volume_7d,
            growth_rate_7d=p.growth_rate_7d,
            competition_count=p.competition_count,
            avg_competitor_rating=p.avg_competitor_rating,
            search_volume=p.search_volume,
            score=p.score,
            scanned_at=p.scanned_at,
        )
        for p in products
    ]


@router.get("/shortlist", response_model=list[ShortlistItemResponse])
async def get_shortlist(
    limit: int = Query(default=20, ge=1, le=100),
    min_margin: float = Query(default=0.0, ge=0.0),
    db: AsyncSession = Depends(get_db),
) -> list[ShortlistItemResponse]:
    """Get today's product shortlist with margin estimates.

    Returns top-scored products that have supplier matches,
    sorted by score descending.
    """
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    # Products with source candidates (i.e., suppliers matched)
    stmt = (
        select(TrendingProduct)
        .options(selectinload(TrendingProduct.source_candidates))
        .where(TrendingProduct.scanned_at >= today_start)
        .where(TrendingProduct.score > 0)
        .order_by(TrendingProduct.score.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    products = result.scalars().unique().all()

    shortlist: list[ShortlistItemResponse] = []
    for p in products:
        candidates = p.source_candidates or []
        best_margin = max((c.estimated_margin for c in candidates), default=None)
        best_price = min(
            (float(c.wholesale_price) for c in candidates), default=None
        )

        if min_margin > 0 and (best_margin is None or best_margin < min_margin):
            continue

        shortlist.append(
            ShortlistItemResponse(
                id=str(p.id),
                name=p.name,
                category=p.category,
                score=p.score,
                growth_rate_7d=p.growth_rate_7d,
                sales_volume_7d=p.sales_volume_7d,
                competition_count=p.competition_count,
                best_margin=float(best_margin) if best_margin else None,
                best_wholesale_price=float(best_price) if best_price else None,
                supplier_count=len(candidates),
                scanned_at=p.scanned_at,
            )
        )

    return shortlist


@router.get("/shortlist/{product_id}", response_model=ProductBriefResponse)
async def get_product_brief(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProductBriefResponse:
    """Get detailed product brief for a shortlisted candidate.

    Includes market analysis, sourcing summary, margin estimate,
    and supplier details.
    """
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product ID format",
        )

    # Fetch product with relationships
    stmt = (
        select(TrendingProduct)
        .options(
            selectinload(TrendingProduct.source_candidates),
            selectinload(TrendingProduct.briefs),
        )
        .where(TrendingProduct.id == pid)
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Get the latest brief
    brief = max(product.briefs, key=lambda b: b.created_at) if product.briefs else None

    # Build supplier info
    suppliers = [
        SupplierInfo(
            supplier_name=c.supplier_name,
            wholesale_price=float(c.wholesale_price),
            moq=c.moq,
            supplier_rating=c.supplier_rating,
            delivery_location=c.delivery_location,
            estimated_landed_cost=float(c.estimated_landed_cost),
            estimated_margin=float(c.estimated_margin),
            status=c.status.value if isinstance(c.status, SourceCandidateStatus) else c.status,
        )
        for c in (product.source_candidates or [])
    ]

    return ProductBriefResponse(
        id=str(brief.id) if brief else str(product.id),
        product_id=str(product.id),
        product_name=product.name,
        category=product.category,
        score=product.score,
        market_analysis=brief.market_analysis if brief else "暂无分析，请触发Brief生成",
        sourcing_summary=brief.sourcing_summary if brief else "暂无",
        margin_estimate=brief.margin_estimate if brief else 0.0,
        recommended_action=brief.recommended_action if brief else "待分析",
        operator_decision=(
            brief.operator_decision.value
            if brief and isinstance(brief.operator_decision, OperatorDecision)
            else (brief.operator_decision if brief else "pending")
        ),
        suppliers=suppliers,
        scanned_at=product.scanned_at,
    )


@router.post("/shortlist/{product_id}/approve", response_model=dict)
async def approve_candidate(
    product_id: str,
    body: DecisionRequest = DecisionRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Operator approves a candidate product for sourcing.

    Updates the product brief decision and source candidate statuses.
    """
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product ID format",
        )

    # Update brief decision
    stmt = (
        select(ProductBrief)
        .where(ProductBrief.trending_product_id == pid)
        .order_by(ProductBrief.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    brief = result.scalar_one_or_none()

    if brief:
        brief.operator_decision = OperatorDecision.APPROVED

    # Update source candidates to approved status
    candidate_stmt = select(SourceCandidate).where(
        SourceCandidate.trending_product_id == pid,
        SourceCandidate.status == SourceCandidateStatus.IDENTIFIED,
    )
    candidate_result = await db.execute(candidate_stmt)
    candidates = candidate_result.scalars().all()

    for candidate in candidates:
        candidate.status = SourceCandidateStatus.APPROVED

    await db.flush()

    return {
        "status": "approved",
        "product_id": product_id,
        "candidates_updated": len(candidates),
        "reason": body.reason,
    }


@router.post("/shortlist/{product_id}/reject", response_model=dict)
async def reject_candidate(
    product_id: str,
    body: DecisionRequest = DecisionRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Operator rejects a candidate product.

    Updates the product brief decision and source candidate statuses.
    """
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product ID format",
        )

    # Update brief decision
    stmt = (
        select(ProductBrief)
        .where(ProductBrief.trending_product_id == pid)
        .order_by(ProductBrief.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    brief = result.scalar_one_or_none()

    if brief:
        brief.operator_decision = OperatorDecision.REJECTED

    # Update source candidates
    candidate_stmt = select(SourceCandidate).where(
        SourceCandidate.trending_product_id == pid,
        SourceCandidate.status == SourceCandidateStatus.IDENTIFIED,
    )
    candidate_result = await db.execute(candidate_stmt)
    candidates = candidate_result.scalars().all()

    for candidate in candidates:
        candidate.status = SourceCandidateStatus.REJECTED

    await db.flush()

    return {
        "status": "rejected",
        "product_id": product_id,
        "candidates_updated": len(candidates),
        "reason": body.reason,
    }


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_manual_scan(
    db: AsyncSession = Depends(get_db),
) -> ScanTriggerResponse:
    """Trigger a manual product discovery scan.

    Enqueues the daily scan task for immediate execution.
    Returns the Celery task ID for tracking.
    """
    from app.modules.discovery.tasks import daily_scan_task

    task = daily_scan_task.apply_async(queue="discovery")

    return ScanTriggerResponse(
        task_id=task.id,
        status="queued",
        message="Discovery scan has been queued for execution",
    )


@router.get("/stats", response_model=StatsResponse)
async def get_discovery_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Get discovery module statistics.

    Returns counts of candidates found/approved/rejected,
    average margins, and top categories.
    """
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    # Total candidates
    total_stmt = select(func.count(TrendingProduct.id))
    total_result = await db.execute(total_stmt)
    total_candidates = total_result.scalar() or 0

    # Decision counts from briefs
    approved_stmt = select(func.count(ProductBrief.id)).where(
        ProductBrief.operator_decision == OperatorDecision.APPROVED
    )
    approved_result = await db.execute(approved_stmt)
    approved_count = approved_result.scalar() or 0

    rejected_stmt = select(func.count(ProductBrief.id)).where(
        ProductBrief.operator_decision == OperatorDecision.REJECTED
    )
    rejected_result = await db.execute(rejected_stmt)
    rejected_count = rejected_result.scalar() or 0

    pending_stmt = select(func.count(ProductBrief.id)).where(
        ProductBrief.operator_decision == OperatorDecision.PENDING
    )
    pending_result = await db.execute(pending_stmt)
    pending_count = pending_result.scalar() or 0

    # Average margin from source candidates
    margin_stmt = select(func.avg(SourceCandidate.estimated_margin))
    margin_result = await db.execute(margin_stmt)
    avg_margin = float(margin_result.scalar() or 0.0)

    # Top categories
    category_stmt = (
        select(
            TrendingProduct.category,
            func.count(TrendingProduct.id).label("count"),
            func.avg(TrendingProduct.score).label("avg_score"),
        )
        .group_by(TrendingProduct.category)
        .order_by(func.count(TrendingProduct.id).desc())
        .limit(10)
    )
    category_result = await db.execute(category_stmt)
    top_categories = [
        {"category": row[0], "count": row[1], "avg_score": round(float(row[2] or 0), 2)}
        for row in category_result.all()
    ]

    # Scans today
    scans_today_stmt = select(func.count(TrendingProduct.id)).where(
        TrendingProduct.scanned_at >= today_start
    )
    scans_today_result = await db.execute(scans_today_stmt)
    scans_today = scans_today_result.scalar() or 0

    return StatsResponse(
        total_candidates=total_candidates,
        approved_count=approved_count,
        rejected_count=rejected_count,
        pending_count=pending_count,
        avg_margin=round(avg_margin, 2),
        top_categories=top_categories,
        scans_today=scans_today,
    )
