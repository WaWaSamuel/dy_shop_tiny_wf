"""Result-oriented endpoints for the ecommerce result console."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import mean
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_ecommerce_user_id, get_redis
from app.services.session_sources import SessionSourceService

router = APIRouter()

_TZ = ZoneInfo("Asia/Shanghai")


class CatalogItemInput(BaseModel):
    id: str
    catalog_key: str | None = None
    name: str
    sku: str
    shop_name: str
    category: str
    supplier: str
    source: str
    price: float | None = None
    cost: float | None = None
    stock: int | None = None
    status_text: str
    listing_status: Literal["active", "pending", "inactive", "unknown"]
    updated_at: str


class CatalogResultSnapshotRequest(BaseModel):
    items: list[CatalogItemInput] = Field(default_factory=list)


class GuardStatusResponse(BaseModel):
    checked_at: str
    environment: str
    allow_development_flow: bool
    allow_business_flow: bool
    allow_external_flow: bool
    guard_level: Literal["ready", "warning", "blocked"]
    summary: str
    blocking_reasons: list[str]
    sources: list[dict[str, Any]]


class BreakdownEntry(BaseModel):
    key: str
    label: str
    count: int


class QualityFinding(BaseModel):
    label: str
    count: int


class QualityReview(BaseModel):
    score: int
    risk_level: Literal["low", "medium", "high"]
    summary: str
    findings: list[QualityFinding]


class CandidateHighlight(BaseModel):
    catalog_key: str
    name: str
    sku: str
    category: str
    listing_status: Literal["active", "pending", "inactive", "unknown"]
    price: float | None = None
    cost: float | None = None
    stock: int | None = None
    score: float
    reasons: list[str]


class CandidateHighlights(BaseModel):
    summary: str
    recommended_catalog_key: str | None = None
    items: list[CandidateHighlight]


class WorkItemSummary(BaseModel):
    catalog_key: str
    name: str
    shop_name: str
    listing_status: Literal["active", "pending", "inactive", "unknown"]
    current_stage_key: str
    current_stage_label: str
    risk_level: Literal["low", "medium", "high"]
    latest_result: str
    recommended_focus: str
    updated_at: str


class CatalogResultSnapshotResponse(BaseModel):
    generated_at: str
    summary: str
    total_items: int
    healthy_items: int
    attention_count: int
    status_breakdown: list[BreakdownEntry]
    stage_breakdown: list[BreakdownEntry]
    quality_review: QualityReview
    candidate_highlights: CandidateHighlights
    recommended_focus: list[str]
    work_items: list[WorkItemSummary]


def _now() -> str:
    return datetime.now(_TZ).isoformat()


def _risk_level(score: int) -> Literal["low", "medium", "high"]:
    if score >= 84:
        return "low"
    if score >= 68:
        return "medium"
    return "high"


def _derive_stage(item: CatalogItemInput) -> tuple[str, str]:
    stock = item.stock or 0
    if item.listing_status == "pending":
        return "pending_review", "待上架结果待确认"
    if item.listing_status == "inactive":
        return "inactive_cleanup", "下架结果待处理"
    if item.listing_status == "unknown":
        return "data_completion", "资料待补齐"
    if stock <= 10:
        return "risk_watch", "低库存经营关注"
    return "stable_operation", "结果已稳定"


def _derive_item_risk(item: CatalogItemInput) -> Literal["low", "medium", "high"]:
    stock = item.stock or 0
    if item.price in (None, 0) or item.cost is None or item.listing_status in {"inactive", "unknown"}:
        return "high"
    if stock <= 10 or item.listing_status == "pending":
        return "medium"
    return "low"


def _build_quality_review(items: list[CatalogItemInput]) -> QualityReview:
    total = len(items)
    missing_price = [item for item in items if item.price in (None, 0)]
    missing_cost = [item for item in items if item.cost is None]
    low_stock = [item for item in items if (item.stock or 0) <= 10]

    seen: set[str] = set()
    duplicate_count = 0
    for item in items:
        dedupe_key = item.catalog_key or item.sku or item.id
        if dedupe_key in seen:
            duplicate_count += 1
        seen.add(dedupe_key)

    score = max(52, 100 - len(missing_price) * 8 - len(missing_cost) * 6 - len(low_stock) * 4 - duplicate_count * 10)
    risk_level = _risk_level(score)
    summary = f"本轮结果快照覆盖 {total} 条货盘记录，当前接收质量评分 {score}/100。"

    return QualityReview(
        score=score,
        risk_level=risk_level,
        summary=summary,
        findings=[
            QualityFinding(label="缺少售价", count=len(missing_price)),
            QualityFinding(label="缺少成本", count=len(missing_cost)),
            QualityFinding(label="低库存关注", count=len(low_stock)),
            QualityFinding(label="重复风险", count=duplicate_count),
        ],
    )


def _build_candidate_highlights(items: list[CatalogItemInput]) -> CandidateHighlights:
    ranked: list[CandidateHighlight] = []

    for item in items:
        price = item.price or 0
        cost = item.cost or 0
        stock = item.stock or 0
        margin_rate = ((price - cost) / price * 100) if price > 0 and cost >= 0 else 0
        score = 52.0
        score += min(margin_rate, 45) * 0.8
        if item.listing_status == "pending":
            score += 18
        elif item.listing_status == "unknown":
            score += 12
        elif item.listing_status == "active":
            score += 6
        if 10 <= stock <= 300:
            score += 10
        elif stock < 10:
            score -= 8
        if "数码" in item.category or "美妆" in item.category or "运动" in item.category:
            score += 6

        reasons: list[str] = []
        if margin_rate >= 55:
            reasons.append("利润空间较好")
        if item.listing_status == "pending":
            reasons.append("待上架，适合优先复看")
        if 10 <= stock <= 300:
            reasons.append("库存压力适中")
        if item.price in (None, 0) or item.cost is None:
            reasons.append("资料未齐，先补数再判断")
        if not reasons:
            reasons.append("建议人工复看后决定是否推进")

        ranked.append(
            CandidateHighlight(
                catalog_key=item.catalog_key or item.id,
                name=item.name,
                sku=item.sku,
                category=item.category,
                listing_status=item.listing_status,
                price=item.price,
                cost=item.cost,
                stock=item.stock,
                score=round(score, 1),
                reasons=reasons,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    highlights = ranked[:5]
    recommended_catalog_key = highlights[0].catalog_key if highlights else None

    if highlights:
        avg_score = round(mean(item.score for item in highlights), 1)
        summary = f"结果看板识别出 {len(highlights)} 个值得优先复看的候选货品，候选均分 {avg_score}。"
    else:
        summary = "当前没有足够清晰的候选亮点，建议先补齐资料并整理待上架货品。"

    return CandidateHighlights(
        summary=summary,
        recommended_catalog_key=recommended_catalog_key,
        items=highlights,
    )


def _build_recommended_focus(
    quality_review: QualityReview,
    candidate_highlights: CandidateHighlights,
    items: list[CatalogItemInput],
) -> list[str]:
    focus: list[str] = []
    finding_map = {item.label: item.count for item in quality_review.findings}
    pending_count = sum(1 for item in items if item.listing_status == "pending")
    inactive_count = sum(1 for item in items if item.listing_status == "inactive")

    if finding_map.get("缺少售价", 0):
        focus.append("先补齐缺少售价的货品，避免结果看板出现不可判断条目。")
    if finding_map.get("缺少成本", 0):
        focus.append("先补齐缺少成本的数据，保证利润判断和风险排序可信。")
    if pending_count:
        focus.append(f"当前有 {pending_count} 条待上架结果，适合优先进入人工复看。")
    if inactive_count:
        focus.append(f"当前有 {inactive_count} 条已下架结果，建议确认是否归档或重新整理。")
    if candidate_highlights.recommended_catalog_key:
        focus.append("优先查看高分候选货品的详情页与完整工作轨迹。")

    return focus[:4] or ["当前结果较稳定，建议优先查看最新更新的货品轨迹。"]


def _build_work_items(items: list[CatalogItemInput]) -> list[WorkItemSummary]:
    rows: list[WorkItemSummary] = []

    for item in items:
        stage_key, stage_label = _derive_stage(item)
        risk_level = _derive_item_risk(item)
        latest_result = item.status_text or "已接收最新结果"
        if risk_level == "high":
            recommended_focus = "优先补齐资料或处理异常状态"
        elif risk_level == "medium":
            recommended_focus = "建议跟进库存与待确认状态"
        else:
            recommended_focus = "当前可继续观察结果变化"

        rows.append(
            WorkItemSummary(
                catalog_key=item.catalog_key or item.id,
                name=item.name,
                shop_name=item.shop_name,
                listing_status=item.listing_status,
                current_stage_key=stage_key,
                current_stage_label=stage_label,
                risk_level=risk_level,
                latest_result=latest_result,
                recommended_focus=recommended_focus,
                updated_at=item.updated_at,
            )
        )

    rows.sort(key=lambda item: (item.risk_level != "high", item.risk_level != "medium", item.updated_at), reverse=False)
    return rows[:20]


@router.get("/guard-status", response_model=GuardStatusResponse)
async def get_guard_status(
    refresh: bool = Query(default=False),
    redis=Depends(get_redis),
    user_id: str = Depends(get_current_ecommerce_user_id),
) -> GuardStatusResponse:
    """Return current guard status for the result console."""
    del user_id
    service = SessionSourceService()
    sources = await service.list_sources(redis=redis, refresh=refresh)
    unhealthy = [item for item in sources if item.get("enabled", True) and not item.get("healthy")]
    stale = [item for item in sources if item.get("is_stale")]

    allow_development_flow = True
    allow_business_flow = True
    allow_external_flow = len(unhealthy) == 0

    if not sources:
        level: Literal["ready", "warning", "blocked"] = "warning"
        summary = "当前没有外部会话源配置，开发链和本地业务链可继续，跨站点链路暂不判断。"
        blocking_reasons: list[str] = []
    elif unhealthy:
        level = "warning"
        names = "、".join(str(item.get("name")) for item in unhealthy)
        summary = f"检测到外部会话源异常：{names}。本地结果展示可继续，跨站点链路建议先恢复登录态。"
        blocking_reasons = [f"{item.get('name')}：{item.get('message')}" for item in unhealthy]
    elif stale:
        level = "warning"
        names = "、".join(str(item.get("name")) for item in stale)
        summary = f"外部会话源 {names} 当前可用，但状态已陈旧，建议刷新后再读取最新外部结果。"
        blocking_reasons = []
    else:
        level = "ready"
        summary = "守门检查通过，可继续结果展示链、本地业务链和外部结果读取。"
        blocking_reasons = []

    return GuardStatusResponse(
        checked_at=_now(),
        environment="debug-fallback",
        allow_development_flow=allow_development_flow,
        allow_business_flow=allow_business_flow,
        allow_external_flow=allow_external_flow,
        guard_level=level,
        summary=summary,
        blocking_reasons=blocking_reasons,
        sources=sources,
    )


@router.post("/catalog-result-snapshot", response_model=CatalogResultSnapshotResponse)
async def build_catalog_result_snapshot(
    payload: CatalogResultSnapshotRequest,
    user_id: str = Depends(get_current_ecommerce_user_id),
) -> CatalogResultSnapshotResponse:
    """Build a result snapshot for catalog items without triggering business execution."""
    del user_id
    items = payload.items

    if not items:
        empty_review = QualityReview(
            score=100,
            risk_level="low",
            summary="当前还没有接收到货盘结果，先导入或写入结果数据后再查看结果快照。",
            findings=[],
        )
        empty_candidates = CandidateHighlights(
            summary="暂无候选亮点，等待结果写入。",
            recommended_catalog_key=None,
            items=[],
        )
        return CatalogResultSnapshotResponse(
            generated_at=_now(),
            summary="结果展示台当前还没有可展示的货盘结果。",
            total_items=0,
            healthy_items=0,
            attention_count=0,
            status_breakdown=[],
            stage_breakdown=[],
            quality_review=empty_review,
            candidate_highlights=empty_candidates,
            recommended_focus=["先导入货盘结果或接入真实 agent 输出。"],
            work_items=[],
        )

    quality_review = _build_quality_review(items)
    candidate_highlights = _build_candidate_highlights(items)
    work_items = _build_work_items(items)

    status_counter = Counter(item.listing_status for item in items)
    stage_counter = Counter(_derive_stage(item)[0] for item in items)
    stage_labels = {key: label for key, label in (_derive_stage(item) for item in items)}

    status_labels = {
        "active": "已上架",
        "pending": "待上架",
        "inactive": "已下架",
        "unknown": "待确认",
    }

    status_breakdown = [
        BreakdownEntry(key=key, label=status_labels.get(key, key), count=count)
        for key, count in status_counter.items()
    ]
    status_breakdown.sort(key=lambda item: item.count, reverse=True)

    stage_breakdown = [
        BreakdownEntry(key=key, label=stage_labels.get(key, key), count=count)
        for key, count in stage_counter.items()
    ]
    stage_breakdown.sort(key=lambda item: item.count, reverse=True)

    attention_count = sum(1 for item in work_items if item.risk_level in {"medium", "high"})
    healthy_items = sum(1 for item in work_items if item.risk_level == "low")
    recommended_focus = _build_recommended_focus(quality_review, candidate_highlights, items)
    summary = (
        f"结果展示台当前已接收 {len(items)} 条货盘结果，"
        f"其中 {healthy_items} 条较稳定，{attention_count} 条需要优先关注。"
    )

    return CatalogResultSnapshotResponse(
        generated_at=_now(),
        summary=summary,
        total_items=len(items),
        healthy_items=healthy_items,
        attention_count=attention_count,
        status_breakdown=status_breakdown,
        stage_breakdown=stage_breakdown,
        quality_review=quality_review,
        candidate_highlights=candidate_highlights,
        recommended_focus=recommended_focus,
        work_items=work_items,
    )
