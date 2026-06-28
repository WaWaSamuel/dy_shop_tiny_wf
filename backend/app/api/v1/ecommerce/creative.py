"""Creative asset endpoints: AI generation, pipeline management, versioning."""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_ecommerce_user_id, get_db, get_read_db, get_redis

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AssetType(str, Enum):
    """Types of creative assets."""

    IMAGE = "image"
    VIDEO = "video"
    COPY = "copy"
    TEMPLATE = "template"


class GenerationProvider(str, Enum):
    """AI generation providers."""

    OPENAI_DALLE = "openai_dalle"
    STABILITY = "stability"
    MIDJOURNEY = "midjourney"
    INTERNAL = "internal"


class PipelineStatus(str, Enum):
    """Status of a creative pipeline job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerateRequest(BaseModel):
    """Request to generate a creative asset via AI."""

    prompt: str = Field(..., min_length=1, max_length=2000)
    asset_type: AssetType = AssetType.IMAGE
    provider: GenerationProvider = GenerationProvider.OPENAI_DALLE
    style: Optional[str] = None
    dimensions: Optional[Dict[str, int]] = None  # e.g. {"width": 1024, "height": 1024}
    product_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class AssetResponse(BaseModel):
    """Creative asset returned to client."""

    id: UUID
    owner_id: str
    asset_type: str
    provider: str
    prompt: str
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    version: int
    status: str
    product_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class AssetVersionResponse(BaseModel):
    """A single version of an asset."""

    version: int
    url: str
    prompt: str
    provider: str
    created_at: str


class PipelineCreate(BaseModel):
    """Create a creative pipeline (batch generation)."""

    name: str = Field(..., max_length=200)
    product_id: Optional[UUID] = None
    steps: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Ordered list of generation steps. Each step has provider, prompt, asset_type.",
    )


class PipelineResponse(BaseModel):
    """Pipeline status response."""

    id: UUID
    name: str
    owner_id: str
    product_id: Optional[UUID]
    status: str
    steps_total: int
    steps_completed: int
    results: List[Dict[str, Any]]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MockGenerateRequest(BaseModel):
    """Local mock generation request used before real providers are connected."""

    category: str = Field(..., min_length=1, max_length=100)
    pipeline: str = Field(..., min_length=1, max_length=100)
    engine: str = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., min_length=1, max_length=2000)
    system_words: List[str] = Field(default_factory=list)


class MockVersionResponse(BaseModel):
    """Single mock version card."""

    id: str
    thumbnail: str
    prompt: str
    engine: str
    timestamp: str
    starred: bool
    status: str
    category: str
    pipeline: str


class MockGenerateResponse(BaseModel):
    """Mock creative generation batch."""

    generated_at: str
    summary: str
    versions: List[MockVersionResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=AssetResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_asset(
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Submit a creative asset generation request.

    The generation is queued for async processing via Celery.
    Returns the asset record with status 'queued'.
    """
    from sqlalchemy import text

    # Persist the asset record
    query = text(
        """
        INSERT INTO creative_assets
            (owner_id, asset_type, provider, prompt, status, version, product_id, metadata)
        VALUES
            (:owner_id, :asset_type, :provider, :prompt, 'queued', 1, :product_id, :metadata)
        RETURNING *
        """
    )
    row = (
        await db.execute(
            query,
            {
                "owner_id": user_id,
                "asset_type": payload.asset_type.value,
                "provider": payload.provider.value,
                "prompt": payload.prompt,
                "product_id": str(payload.product_id) if payload.product_id else None,
                "metadata": payload.metadata or {},
            },
        )
    ).mappings().first()

    # Enqueue Celery task (fire-and-forget)
    # In production: celery_app.send_task("tasks.generate_creative", args=[str(row["id"])])
    # For now, publish to Redis as a lightweight job queue signal
    await redis.lpush(
        "creative:generation:queue",
        str(row["id"]),
    )

    return AssetResponse(**dict(row))


@router.post("/mock-generate", response_model=MockGenerateResponse)
async def mock_generate_asset(
    payload: MockGenerateRequest,
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Return local mock versions for the creative studio page."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    del user_id
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    batch_id = now.strftime("%Y%m%d%H%M%S")
    palette = ["667eea", "764ba2", "f093fb"]
    prompt_prefix = "，".join([*payload.system_words, payload.prompt].copy()).strip("，")

    versions = [
        MockVersionResponse(
            id=f"{batch_id}-{index + 1}",
            thumbnail=f"https://via.placeholder.com/320x320/{color}/fff?text=G{index + 1}",
            prompt=f"{prompt_prefix} · 方案 {index + 1}",
            engine=payload.engine,
            timestamp=now.isoformat(),
            starred=False,
            status="completed",
            category=payload.category,
            pipeline=payload.pipeline,
        )
        for index, color in enumerate(palette)
    ]

    return MockGenerateResponse(
        generated_at=now.isoformat(),
        summary=f"已生成 3 个 mock 素材版本，可继续在前端预览、收藏和比对。",
        versions=versions,
    )


@router.get("", response_model=List[AssetResponse])
async def list_assets(
    asset_type: Optional[AssetType] = None,
    product_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """List creative assets for the current user."""
    from sqlalchemy import text

    conditions = ["owner_id = :owner_id"]
    params: dict = {"owner_id": user_id}

    if asset_type:
        conditions.append("asset_type = :asset_type")
        params["asset_type"] = asset_type.value
    if product_id:
        conditions.append("product_id = :product_id")
        params["product_id"] = str(product_id)

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_size
    query = text(
        f"SELECT * FROM creative_assets WHERE {where_clause} "
        f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    )
    params["limit"] = page_size
    params["offset"] = offset
    rows = (await db.execute(query, params)).mappings().all()
    return [AssetResponse(**dict(r)) for r in rows]


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Get a single creative asset."""
    from sqlalchemy import text

    query = text(
        "SELECT * FROM creative_assets WHERE id = :id AND owner_id = :owner_id"
    )
    row = (await db.execute(query, {"id": str(asset_id), "owner_id": user_id})).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return AssetResponse(**dict(row))


@router.get("/{asset_id}/versions", response_model=List[AssetVersionResponse])
async def list_asset_versions(
    asset_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Get version history for a creative asset."""
    from sqlalchemy import text

    query = text(
        "SELECT version, url, prompt, provider, created_at "
        "FROM creative_asset_versions "
        "WHERE asset_id = :asset_id AND owner_id = :owner_id "
        "ORDER BY version DESC"
    )
    rows = (
        await db.execute(query, {"asset_id": str(asset_id), "owner_id": user_id})
    ).mappings().all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return [AssetVersionResponse(**dict(r)) for r in rows]


@router.post("/{asset_id}/regenerate", response_model=AssetResponse, status_code=status.HTTP_202_ACCEPTED)
async def regenerate_asset(
    asset_id: UUID,
    new_prompt: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Regenerate an asset, creating a new version."""
    from sqlalchemy import text

    # Fetch existing
    fetch_q = text(
        "SELECT * FROM creative_assets WHERE id = :id AND owner_id = :owner_id"
    )
    existing = (
        await db.execute(fetch_q, {"id": str(asset_id), "owner_id": user_id})
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    # Bump version
    prompt = new_prompt or existing["prompt"]
    new_version = existing["version"] + 1

    update_q = text(
        "UPDATE creative_assets SET version = :version, prompt = :prompt, "
        "status = 'queued', updated_at = NOW() "
        "WHERE id = :id RETURNING *"
    )
    row = (
        await db.execute(update_q, {"version": new_version, "prompt": prompt, "id": str(asset_id)})
    ).mappings().first()

    await redis.lpush("creative:generation:queue", str(asset_id))
    return AssetResponse(**dict(row))


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------


@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    payload: PipelineCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Create a multi-step creative generation pipeline."""
    from sqlalchemy import text

    query = text(
        """
        INSERT INTO creative_pipelines
            (owner_id, name, product_id, status, steps_total, steps_completed, results)
        VALUES
            (:owner_id, :name, :product_id, 'queued', :steps_total, 0, '[]')
        RETURNING *
        """
    )
    row = (
        await db.execute(
            query,
            {
                "owner_id": user_id,
                "name": payload.name,
                "product_id": str(payload.product_id) if payload.product_id else None,
                "steps_total": len(payload.steps),
            },
        )
    ).mappings().first()

    # Queue pipeline for processing
    await redis.lpush("creative:pipeline:queue", str(row["id"]))
    return PipelineResponse(**dict(row))


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline_status(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_ecommerce_user_id),
):
    """Check the status of a creative pipeline."""
    from sqlalchemy import text

    query = text(
        "SELECT * FROM creative_pipelines WHERE id = :id AND owner_id = :owner_id"
    )
    row = (
        await db.execute(query, {"id": str(pipeline_id), "owner_id": user_id})
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return PipelineResponse(**dict(row))
