"""Analytics endpoints for ecommerce data."""

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_ecommerce_user_id, get_read_db, get_redis

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MetricType(str, Enum):
    """Available metric types."""

    REVENUE = "revenue"
    ORDERS = "orders"
    CONVERSION_RATE = "conversion_rate"
    AVG_ORDER_VALUE = "avg_order_value"
    UNITS_SOLD = "units_sold"
    PROFIT_MARGIN = "profit_margin"
    RETURN_RATE = "return_rate"


class Granularity(str, Enum):
    """Time series granularity."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TimeSeriesPoint(BaseModel):
    """Single data point in a time series."""

    timestamp: str
    value: float


class MetricSummary(BaseModel):
    """Summary of a single metric."""

    metric: str
    current_value: float
    previous_value: float
    change_percent: float
    trend: str  # "up", "down", "flat"


class DashboardResponse(BaseModel):
    """Dashboard overview response."""

    period_start: str
    period_end: str
    metrics: List[MetricSummary]


class TimeSeriesResponse(BaseModel):
    """Time series data response."""

    metric: str
    granularity: str
    period_start: str
    period_end: str
    data_points: List[TimeSeriesPoint]


class TopProductResponse(BaseModel):
    """Top performing product."""

    product_id: UUID
    title: str
    revenue: float
    units_sold: int
    orders_count: int


class ChannelBreakdownItem(BaseModel):
    """Revenue breakdown by channel."""

    channel: str
    revenue: float
    orders_count: int
    percentage: float


class AnalyticsExportRequest(BaseModel):
    """Request to export analytics data."""

    metrics: List[MetricType]
    start_date: date
    end_date: date
    granularity: Granularity = Granularity.DAILY
    format: str = Field("csv", pattern="^(csv|json)$")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_read_db),
    redis=Depends(get_redis),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Get dashboard overview with key metrics and period-over-period comparison.

    Uses Redis caching with a 5-minute TTL to reduce DB load.
    """
    import json

    cache_key = f"analytics:dashboard:{user_id}:{days}"
    cached = await redis.get(cache_key)
    if cached:
        return DashboardResponse(**json.loads(cached))

    from sqlalchemy import text

    now = datetime.utcnow()
    period_end = now
    period_start = now - timedelta(days=days)
    prev_start = period_start - timedelta(days=days)

    # Current period metrics
    current_q = text(
        """
        SELECT
            COALESCE(SUM(total_amount), 0) AS revenue,
            COUNT(*) AS orders_count,
            COALESCE(AVG(total_amount), 0) AS avg_order_value
        FROM orders
        WHERE owner_id = :owner_id
            AND created_at >= :start AND created_at <= :end
            AND status NOT IN ('cancelled', 'refunded')
        """
    )
    current = (
        await db.execute(
            current_q,
            {"owner_id": user_id, "start": period_start, "end": period_end},
        )
    ).mappings().first()

    # Previous period metrics
    previous = (
        await db.execute(
            current_q,
            {"owner_id": user_id, "start": prev_start, "end": period_start},
        )
    ).mappings().first()

    def calc_change(current_val: float, prev_val: float) -> tuple:
        if prev_val == 0:
            return (100.0 if current_val > 0 else 0.0, "up" if current_val > 0 else "flat")
        change = ((current_val - prev_val) / prev_val) * 100
        trend = "up" if change > 1 else ("down" if change < -1 else "flat")
        return (round(change, 2), trend)

    metrics: List[MetricSummary] = []

    # Revenue
    rev_change, rev_trend = calc_change(float(current["revenue"]), float(previous["revenue"]))
    metrics.append(
        MetricSummary(
            metric="revenue",
            current_value=float(current["revenue"]),
            previous_value=float(previous["revenue"]),
            change_percent=rev_change,
            trend=rev_trend,
        )
    )

    # Orders
    ord_change, ord_trend = calc_change(float(current["orders_count"]), float(previous["orders_count"]))
    metrics.append(
        MetricSummary(
            metric="orders",
            current_value=float(current["orders_count"]),
            previous_value=float(previous["orders_count"]),
            change_percent=ord_change,
            trend=ord_trend,
        )
    )

    # Average order value
    aov_change, aov_trend = calc_change(float(current["avg_order_value"]), float(previous["avg_order_value"]))
    metrics.append(
        MetricSummary(
            metric="avg_order_value",
            current_value=round(float(current["avg_order_value"]), 2),
            previous_value=round(float(previous["avg_order_value"]), 2),
            change_percent=aov_change,
            trend=aov_trend,
        )
    )

    response = DashboardResponse(
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        metrics=metrics,
    )

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, response.model_dump_json())
    return response


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    metric: MetricType = MetricType.REVENUE,
    granularity: Granularity = Granularity.DAILY,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Get time series data for a specific metric."""
    from sqlalchemy import text

    now = datetime.utcnow()
    period_start = now - timedelta(days=days)

    # Map granularity to PostgreSQL date_trunc
    trunc_map = {
        Granularity.HOURLY: "hour",
        Granularity.DAILY: "day",
        Granularity.WEEKLY: "week",
        Granularity.MONTHLY: "month",
    }
    trunc = trunc_map[granularity]

    # Build metric expression
    metric_expr_map = {
        MetricType.REVENUE: "COALESCE(SUM(total_amount), 0)",
        MetricType.ORDERS: "COUNT(*)",
        MetricType.AVG_ORDER_VALUE: "COALESCE(AVG(total_amount), 0)",
        MetricType.UNITS_SOLD: "COALESCE(SUM(oi.quantity), 0)",
    }

    if metric in (MetricType.UNITS_SOLD,):
        # Need join with order_items
        query = text(
            f"""
            SELECT date_trunc(:trunc, o.created_at) AS ts,
                   {metric_expr_map[metric]} AS val
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.owner_id = :owner_id
                AND o.created_at >= :start
                AND o.status NOT IN ('cancelled', 'refunded')
            GROUP BY ts ORDER BY ts
            """
        )
    else:
        metric_expr = metric_expr_map.get(metric, "COUNT(*)")
        query = text(
            f"""
            SELECT date_trunc(:trunc, created_at) AS ts,
                   {metric_expr} AS val
            FROM orders
            WHERE owner_id = :owner_id
                AND created_at >= :start
                AND status NOT IN ('cancelled', 'refunded')
            GROUP BY ts ORDER BY ts
            """
        )

    rows = (
        await db.execute(query, {"trunc": trunc, "owner_id": user_id, "start": period_start})
    ).mappings().all()

    data_points = [
        TimeSeriesPoint(timestamp=str(r["ts"]), value=round(float(r["val"]), 2))
        for r in rows
    ]

    return TimeSeriesResponse(
        metric=metric.value,
        granularity=granularity.value,
        period_start=period_start.isoformat(),
        period_end=now.isoformat(),
        data_points=data_points,
    )


@router.get("/top-products", response_model=List[TopProductResponse])
async def get_top_products(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Get top performing products by revenue."""
    from sqlalchemy import text

    period_start = datetime.utcnow() - timedelta(days=days)

    query = text(
        """
        SELECT
            p.id AS product_id,
            p.title,
            COALESCE(SUM(oi.unit_price * oi.quantity), 0) AS revenue,
            COALESCE(SUM(oi.quantity), 0)::int AS units_sold,
            COUNT(DISTINCT o.id)::int AS orders_count
        FROM products p
        JOIN order_items oi ON oi.product_id = p.id
        JOIN orders o ON o.id = oi.order_id
        WHERE p.owner_id = :owner_id
            AND o.created_at >= :start
            AND o.status NOT IN ('cancelled', 'refunded')
        GROUP BY p.id, p.title
        ORDER BY revenue DESC
        LIMIT :limit
        """
    )
    rows = (
        await db.execute(query, {"owner_id": user_id, "start": period_start, "limit": limit})
    ).mappings().all()

    return [TopProductResponse(**dict(r)) for r in rows]


@router.get("/channels", response_model=List[ChannelBreakdownItem])
async def get_channel_breakdown(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Get revenue breakdown by sales channel."""
    from sqlalchemy import text

    period_start = datetime.utcnow() - timedelta(days=days)

    query = text(
        """
        SELECT
            channel,
            COALESCE(SUM(total_amount), 0) AS revenue,
            COUNT(*)::int AS orders_count
        FROM orders
        WHERE owner_id = :owner_id
            AND created_at >= :start
            AND status NOT IN ('cancelled', 'refunded')
        GROUP BY channel
        ORDER BY revenue DESC
        """
    )
    rows = (
        await db.execute(query, {"owner_id": user_id, "start": period_start})
    ).mappings().all()

    total_revenue = sum(float(r["revenue"]) for r in rows) or 1.0
    return [
        ChannelBreakdownItem(
            channel=r["channel"],
            revenue=float(r["revenue"]),
            orders_count=r["orders_count"],
            percentage=round(float(r["revenue"]) / total_revenue * 100, 2),
        )
        for r in rows
    ]


@router.post("/export")
async def export_analytics(
    payload: AnalyticsExportRequest,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Export analytics data in CSV or JSON format.

    In production, this would generate a file and return a download URL.
    """
    # Validate date range
    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )
    if (payload.end_date - payload.start_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range must not exceed 365 days",
        )

    # In production, this would queue a Celery task for large exports
    return {
        "status": "processing",
        "message": "Export queued. You will receive a download link when ready.",
        "params": {
            "metrics": [m.value for m in payload.metrics],
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
            "granularity": payload.granularity.value,
            "format": payload.format,
        },
    }
