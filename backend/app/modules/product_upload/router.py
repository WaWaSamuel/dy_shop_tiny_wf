"""FastAPI router for Product Upload & Listing endpoints.

Provides REST API endpoints for creating, managing, and publishing
product listings on 抖店.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product, ProductStatus

from .service import (
    BatchResult,
    ProductInput,
    ProductUploadService,
)
from .tasks import (
    auto_publish_task,
    batch_upload_task,
    check_review_status_task,
    upload_product_task,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response schemas
# ─────────────────────────────────────────────────────────────────────────────


class SKUInput(BaseModel):
    """Input schema for a single SKU."""

    name: str = ""
    price: float = 0.0
    market_price: float = 0.0
    stock: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)
    image_url: str | None = None


class ProductCreateRequest(BaseModel):
    """Request body for creating a product listing."""

    name: str = Field(..., min_length=1, max_length=512, description="Product name")
    description: str = Field(default="", max_length=5000)
    images: list[str] = Field(default_factory=list, description="Image file paths or URLs")
    category_id: str | None = Field(default=None, description="Category ID (auto-matched if empty)")
    skus: list[SKUInput] = Field(default_factory=list)
    price: float = Field(default=0.0, ge=0)
    market_price: float = Field(default=0.0, ge=0)
    stock: int = Field(default=0, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    auto_publish: bool = Field(default=False, description="Auto-publish after review approval")
    async_mode: bool = Field(default=True, description="Process via background task")


class BatchUploadRequest(BaseModel):
    """Request body for batch product upload."""

    products: list[ProductCreateRequest] = Field(..., min_length=1, max_length=100)
    async_mode: bool = Field(default=True, description="Process via background tasks")


class ProductResponse(BaseModel):
    """Response schema for a product."""

    id: str
    name: str
    category_id: str
    category_name: str
    description: str
    status: str
    images: list[Any]
    douyin_product_id: str | None
    price_range: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Paginated product list response."""

    total: int
    page: int
    page_size: int
    products: list[ProductResponse]


class ProductStatusResponse(BaseModel):
    """Response for product status check."""

    product_id: str
    douyin_product_id: str | None
    status: str
    listing_submitted_at: str | None
    listing_approved_at: str | None


class BatchUploadResponse(BaseModel):
    """Response for batch upload initiation."""

    total: int
    dispatched: int
    tasks: list[dict[str, Any]]


class ValidationRequest(BaseModel):
    """Request body for pre-flight validation."""

    name: str = Field(..., min_length=1)
    description: str = ""
    images: list[str] = Field(default_factory=list)
    category_id: str | None = None


class ValidationResponse(BaseModel):
    """Response for pre-flight validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    prohibited_words: list[str]
    suggested_category: dict[str, Any] | None = None


class CategoryResponse(BaseModel):
    """Response schema for category tree."""

    id: str
    name: str
    parent_id: str | None
    level: int
    is_leaf: bool
    children: list["CategoryResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True


# Enable self-referential model
CategoryResponse.model_rebuild()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product listing",
    description="Create a new product listing on 抖店. Supports sync and async modes.",
)
async def create_product(
    request: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Create a new product listing.

    In async mode (default), dispatches a background task and returns
    immediately with a DRAFT status product. In sync mode, waits for
    the full pipeline to complete.
    """
    if request.async_mode:
        # Create a draft record and dispatch background task
        product = Product(
            name=request.name,
            category_id=request.category_id or "pending",
            category_name="pending",
            description=request.description,
            status=ProductStatus.DRAFT,
            images=request.images,
            sku_data={"skus": [sku.model_dump() for sku in request.skus]},
            price_range=f"{request.price:.2f}" if request.price else None,
        )
        db.add(product)
        await db.flush()

        # Dispatch async task
        product_data = {
            "name": request.name,
            "description": request.description,
            "images": request.images,
            "category_id": request.category_id,
            "skus": [sku.model_dump() for sku in request.skus],
            "price": request.price,
            "market_price": request.market_price,
            "stock": request.stock,
            "attributes": request.attributes,
            "keywords": request.keywords,
            "auto_publish": request.auto_publish,
        }
        upload_product_task.apply_async(args=[product_data])

        return _product_to_response(product)

    # Sync mode: execute pipeline directly
    service = ProductUploadService(db=db)
    try:
        input_data = ProductInput(
            name=request.name,
            description=request.description,
            images=request.images,
            category_id=request.category_id,
            skus=[sku.model_dump() for sku in request.skus],
            price=request.price,
            market_price=request.market_price,
            stock=request.stock,
            attributes=request.attributes,
            keywords=request.keywords,
            auto_publish=request.auto_publish,
        )
        product = await service.create_product(input_data)
        return _product_to_response(product)
    finally:
        await service.close()


@router.post(
    "/batch",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch upload products",
    description="Upload multiple products with throttling (max 5 concurrent).",
)
async def batch_upload(
    request: BatchUploadRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchUploadResponse:
    """Batch upload multiple products.

    Dispatches individual upload tasks with rate limiting to prevent
    overwhelming the 抖店 API. Returns task IDs for status tracking.
    """
    products_data = [
        {
            "name": p.name,
            "description": p.description,
            "images": p.images,
            "category_id": p.category_id,
            "skus": [sku.model_dump() for sku in p.skus],
            "price": p.price,
            "market_price": p.market_price,
            "stock": p.stock,
            "attributes": p.attributes,
            "keywords": p.keywords,
            "auto_publish": p.auto_publish,
        }
        for p in request.products
    ]

    if request.async_mode:
        result = batch_upload_task.apply_async(args=[products_data])
        return BatchUploadResponse(
            total=len(products_data),
            dispatched=len(products_data),
            tasks=[{"batch_task_id": result.id}],
        )

    # Sync mode: process directly
    service = ProductUploadService(db=db)
    try:
        inputs = [
            ProductInput(**data) for data in products_data
        ]
        batch_result = await service.batch_upload(inputs)
        return BatchUploadResponse(
            total=batch_result.total,
            dispatched=batch_result.succeeded,
            tasks=batch_result.results,
        )
    finally:
        await service.close()


@router.get(
    "/",
    response_model=ProductListResponse,
    summary="List products",
    description="List products with optional status filter and pagination.",
)
async def list_products(
    status_filter: ProductStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    """List products with status filter and pagination."""
    query = select(Product).order_by(Product.created_at.desc())

    if status_filter:
        query = query.where(Product.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    return ProductListResponse(
        total=total,
        page=page,
        page_size=page_size,
        products=[_product_to_response(p) for p in products],
    )


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="Get category tree",
    description="Fetch the full 抖店 product category tree.",
)
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    """Get the 抖店 product category tree."""
    service = ProductUploadService(db=db)
    try:
        categories = await service.get_category_tree()
        return [_category_to_response(c) for c in categories]
    finally:
        await service.close()


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Pre-flight validation",
    description="Validate product data before submission (check images, prohibited words, category).",
)
async def validate_product(
    request: ValidationRequest,
    db: AsyncSession = Depends(get_db),
) -> ValidationResponse:
    """Pre-flight validation of product data.

    Checks images, scans for prohibited words, and suggests category
    without actually submitting anything to 抖店.
    """
    from .content_generator import AIContentGenerator
    from .image_processor import ImageProcessor

    errors: list[str] = []
    warnings: list[str] = []

    # Validate name length
    if len(request.name) > 30:
        warnings.append(
            f"Product name ({len(request.name)} chars) exceeds recommended 30 chars. "
            "Title will be auto-optimized."
        )

    # Check prohibited words
    content_gen = AIContentGenerator()
    prohibited = content_gen.check_prohibited_words(
        f"{request.name} {request.description}"
    )
    if prohibited:
        errors.append(
            f"Prohibited words found: {', '.join(prohibited)}. "
            "These will cause listing rejection."
        )

    # Validate images
    image_processor = ImageProcessor()
    for img_path in request.images:
        result = image_processor.validate_image(img_path)
        if not result.valid:
            errors.extend(
                f"Image '{img_path}': {e}" for e in result.errors
            )
        warnings.extend(
            f"Image '{img_path}': {w}" for w in result.warnings
        )

    if not request.images:
        warnings.append("No images provided. At least one main image is required.")

    # Category suggestion
    suggested_category = None
    if not request.category_id:
        try:
            service = ProductUploadService(db=db)
            match = await service.match_category(request.name, request.description)
            await service.close()
            if match.category_id:
                suggested_category = {
                    "category_id": match.category_id,
                    "category_name": match.category_name,
                    "confidence": match.confidence,
                    "path": match.path,
                }
        except Exception as e:
            warnings.append(f"Category auto-match unavailable: {str(e)}")

    return ValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        prohibited_words=prohibited,
        suggested_category=suggested_category,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product details",
    description="Get detailed information about a specific product.",
)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get product details by ID."""
    product = await _get_product_or_404(product_id, db)
    return _product_to_response(product)


@router.get(
    "/{product_id}/status",
    response_model=ProductStatusResponse,
    summary="Check listing status",
    description="Check the current listing/review status of a product.",
)
async def get_product_status(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProductStatusResponse:
    """Check the current status of a product listing."""
    product = await _get_product_or_404(product_id, db)

    # If the product has a 抖店 ID, optionally poll for latest status
    if product.douyin_product_id:
        service = ProductUploadService(db=db)
        try:
            remote_status = await service.check_product_status(
                product.douyin_product_id
            )
            if remote_status != product.status:
                product.status = remote_status
                await db.flush()
        except Exception as e:
            logger.warning(
                "Failed to poll remote status for %s: %s",
                product.douyin_product_id,
                str(e),
            )
        finally:
            await service.close()

    return ProductStatusResponse(
        product_id=str(product.id),
        douyin_product_id=product.douyin_product_id,
        status=product.status.value if isinstance(product.status, ProductStatus) else product.status,
        listing_submitted_at=(
            product.listing_submitted_at.isoformat()
            if product.listing_submitted_at
            else None
        ),
        listing_approved_at=(
            product.listing_approved_at.isoformat()
            if product.listing_approved_at
            else None
        ),
    )


@router.post(
    "/{product_id}/publish",
    summary="Publish a product",
    description="Manually publish (set online) a product after review approval.",
)
async def publish_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually publish a product."""
    product = await _get_product_or_404(product_id, db)

    if not product.douyin_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product has not been submitted to 抖店 yet.",
        )

    if product.status not in (ProductStatus.APPROVED, ProductStatus.OFFLINE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish product in status '{product.status.value}'. Must be 'approved' or 'offline'.",
        )

    service = ProductUploadService(db=db)
    try:
        success = await service.publish_product(product.douyin_product_id)
        if success:
            product.status = ProductStatus.ONLINE
            await db.flush()
            return {"success": True, "message": "Product published successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to publish product on 抖店.",
            )
    finally:
        await service.close()


@router.post(
    "/{product_id}/offline",
    summary="Take product offline",
    description="Take a product offline (remove from store).",
)
async def take_product_offline(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Take a product offline."""
    product = await _get_product_or_404(product_id, db)

    if not product.douyin_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product has not been submitted to 抖店 yet.",
        )

    if product.status != ProductStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot take offline product in status '{product.status.value}'. Must be 'online'.",
        )

    service = ProductUploadService(db=db)
    try:
        success = await service.take_offline(product.douyin_product_id)
        if success:
            product.status = ProductStatus.OFFLINE
            await db.flush()
            return {"success": True, "message": "Product taken offline successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to take product offline on 抖店.",
            )
    finally:
        await service.close()


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────


async def _get_product_or_404(product_id: str, db: AsyncSession) -> Product:
    """Fetch a product by ID or raise 404."""
    try:
        product_uuid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid product ID format: {product_id}",
        )

    result = await db.execute(
        select(Product).where(Product.id == product_uuid)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product not found: {product_id}",
        )

    return product


def _product_to_response(product: Product) -> ProductResponse:
    """Convert a Product model to a response schema."""
    return ProductResponse(
        id=str(product.id),
        name=product.name,
        category_id=product.category_id,
        category_name=product.category_name,
        description=product.description,
        status=product.status.value if isinstance(product.status, ProductStatus) else product.status,
        images=product.images or [],
        douyin_product_id=product.douyin_product_id,
        price_range=product.price_range,
        created_at=product.created_at.isoformat() if product.created_at else "",
        updated_at=product.updated_at.isoformat() if product.updated_at else "",
    )


def _category_to_response(category) -> CategoryResponse:
    """Convert a Category dataclass to a response schema."""
    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        level=category.level,
        is_leaf=category.is_leaf,
        children=[_category_to_response(c) for c in category.children],
    )
