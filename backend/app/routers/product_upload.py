"""Product upload router placeholder."""

from fastapi import APIRouter, UploadFile

router = APIRouter()

_PRODUCTS = [
    {
        "id": "1",
        "name": "Summer Floral Dress - V-Neck",
        "category": "Women Clothing",
        "status": "online",
        "price": 128.0,
        "sku_count": 6,
        "images": ["/placeholder-1.jpg"],
        "created_at": "2024-06-10T08:00:00Z",
        "updated_at": "2024-06-12T10:00:00Z",
    },
    {
        "id": "2",
        "name": "Casual Denim Jacket - Oversized",
        "category": "Women Clothing",
        "status": "under_review",
        "price": 259.0,
        "sku_count": 4,
        "images": ["/placeholder-2.jpg"],
        "created_at": "2024-06-14T09:00:00Z",
        "updated_at": "2024-06-14T09:30:00Z",
    },
    {
        "id": "3",
        "name": "Minimalist Leather Crossbody Bag",
        "category": "Accessories",
        "status": "approved",
        "price": 189.0,
        "sku_count": 3,
        "images": ["/placeholder-3.jpg"],
        "created_at": "2024-06-13T14:00:00Z",
        "updated_at": "2024-06-15T08:00:00Z",
    },
]


@router.get("/")
async def list_products(status: str | None = None) -> dict[str, object]:
    """List uploaded products."""
    items = _PRODUCTS if not status else [item for item in _PRODUCTS if item["status"] == status]
    return {"items": items, "total": len(items)}


@router.post("/")
async def create_product(payload: dict[str, object]) -> dict[str, object]:
    """Pretend to create a product."""
    return {
        "id": "new-product",
        "name": payload.get("name", "New Product"),
        "category": payload.get("category", "Uncategorized"),
        "status": "draft",
        "price": payload.get("price", 0),
        "sku_count": len(payload.get("skus", [])),
        "images": payload.get("images", []),
        "created_at": "2024-06-15T12:30:00Z",
        "updated_at": "2024-06-15T12:30:00Z",
    }


@router.post("/batch-upload")
async def batch_upload_products(file: UploadFile) -> dict[str, str]:
    """Pretend to accept a batch upload file."""
    return {"filename": file.filename or "unknown", "status": "queued"}


@router.get("/{product_id}/status")
async def product_status(product_id: str) -> dict[str, str]:
    """Return a placeholder product status."""
    return {"id": product_id, "status": "under_review"}


@router.post("/{product_id}/publish")
async def publish_product(product_id: str) -> dict[str, str]:
    """Pretend to publish a product."""
    return {"id": product_id, "status": "online"}
