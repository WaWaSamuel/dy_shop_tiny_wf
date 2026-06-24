"""Product discovery router placeholder."""

from fastapi import APIRouter

router = APIRouter()

_SHORTLIST = [
    {
        "id": "1",
        "product_name": "Viral Ice Silk Cooling Scarf",
        "trend_score": 95,
        "margin_estimate": 62,
        "supplier_info": {"name": "Yiwu Textile Co.", "rating": 4.8, "location": "Zhejiang"},
        "image_url": "/placeholder-product-1.jpg",
        "recommendation_reason": "Rising fast on Douyin with strong weekly search growth.",
        "status": "pending",
    },
    {
        "id": "2",
        "product_name": "Portable Mini Fan - Neck Worn",
        "trend_score": 88,
        "margin_estimate": 55,
        "supplier_info": {"name": "Shenzhen Cool Tech", "rating": 4.6, "location": "Guangdong"},
        "image_url": "/placeholder-product-2.jpg",
        "recommendation_reason": "Seasonal demand is climbing with high daily unit velocity.",
        "status": "pending",
    },
]

_TRENDING = [
    {
        "id": "1",
        "name": "Dopamine Color Block T-Shirt",
        "trend_score": 97,
        "margin_estimate": 45,
        "supplier": "Guangzhou Fabric House",
        "supplier_rating": 4.7,
        "category": "Women Clothing",
        "daily_sales": 12000,
        "source_url": "#",
    },
    {
        "id": "2",
        "name": "Magnetic Phone Case - MagSafe",
        "trend_score": 93,
        "margin_estimate": 58,
        "supplier": "Shenzhen Tech Parts",
        "supplier_rating": 4.5,
        "category": "Electronics",
        "daily_sales": 8500,
        "source_url": "#",
    },
]


@router.get("/")
async def discover_products() -> dict[str, str]:
    """Discover trending products."""
    return {"status": "ok"}


@router.get("/trending")
async def trending_products(category: str | None = None, sort_by: str | None = None) -> dict[str, object]:
    """List trending products."""
    items = _TRENDING if not category else [item for item in _TRENDING if item["category"] == category]
    if sort_by in {"trend_score", "margin_estimate", "daily_sales"}:
        items = sorted(items, key=lambda item: item[sort_by], reverse=True)
    return {"items": items, "total": len(items)}


@router.get("/shortlist")
async def shortlist_candidates() -> dict[str, object]:
    """List curated shortlist candidates."""
    return {"items": _SHORTLIST}


@router.post("/shortlist/{candidate_id}/approve")
async def approve_candidate(candidate_id: str) -> dict[str, str]:
    """Pretend to approve a shortlist candidate."""
    return {"id": candidate_id, "status": "approved"}


@router.post("/shortlist/{candidate_id}/reject")
async def reject_candidate(candidate_id: str) -> dict[str, str]:
    """Pretend to reject a shortlist candidate."""
    return {"id": candidate_id, "status": "rejected"}


@router.post("/scan")
async def trigger_scan() -> dict[str, str]:
    """Pretend to trigger a discovery scan."""
    return {"status": "scan_started"}
