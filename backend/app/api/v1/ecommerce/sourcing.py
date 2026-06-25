"""Sourcing and supplier endpoints with Provider Pattern for multi-source integrations."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db, get_read_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Provider Pattern
# ---------------------------------------------------------------------------


class ProviderType(str, Enum):
    """Supported sourcing providers."""

    ALIBABA = "alibaba"
    MADE_IN_CHINA = "made_in_china"
    GLOBAL_SOURCES = "global_sources"
    MANUAL = "manual"


class SourcingProvider(ABC):
    """Abstract base for sourcing providers."""

    @abstractmethod
    async def search_suppliers(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for suppliers matching the query."""
        ...

    @abstractmethod
    async def get_supplier_detail(self, supplier_id: str) -> Dict[str, Any]:
        """Fetch detailed supplier information."""
        ...

    @abstractmethod
    async def get_product_quotes(self, product_query: str, quantity: int) -> List[Dict[str, Any]]:
        """Get price quotes for a product."""
        ...


class AlibabaProvider(SourcingProvider):
    """Alibaba.com integration provider."""

    async def search_suppliers(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        # In production, this would call the Alibaba API
        return [
            {
                "provider": ProviderType.ALIBABA,
                "supplier_id": "ali_supplier_001",
                "name": f"Alibaba Supplier for '{query}'",
                "rating": 4.8,
                "response_time": "< 24h",
                "min_order": 100,
            }
        ]

    async def get_supplier_detail(self, supplier_id: str) -> Dict[str, Any]:
        return {
            "provider": ProviderType.ALIBABA,
            "supplier_id": supplier_id,
            "name": "Sample Alibaba Supplier",
            "verified": True,
            "years_in_business": 8,
            "location": "Guangzhou, China",
        }

    async def get_product_quotes(self, product_query: str, quantity: int) -> List[Dict[str, Any]]:
        return [
            {
                "provider": ProviderType.ALIBABA,
                "product": product_query,
                "unit_price": 2.50,
                "moq": 100,
                "lead_time_days": 15,
            }
        ]


class MadeInChinaProvider(SourcingProvider):
    """Made-in-China.com integration provider."""

    async def search_suppliers(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        return [
            {
                "provider": ProviderType.MADE_IN_CHINA,
                "supplier_id": "mic_supplier_001",
                "name": f"MIC Supplier for '{query}'",
                "rating": 4.5,
                "response_time": "< 48h",
                "min_order": 50,
            }
        ]

    async def get_supplier_detail(self, supplier_id: str) -> Dict[str, Any]:
        return {
            "provider": ProviderType.MADE_IN_CHINA,
            "supplier_id": supplier_id,
            "name": "Sample MIC Supplier",
            "verified": True,
            "years_in_business": 5,
            "location": "Shenzhen, China",
        }

    async def get_product_quotes(self, product_query: str, quantity: int) -> List[Dict[str, Any]]:
        return [
            {
                "provider": ProviderType.MADE_IN_CHINA,
                "product": product_query,
                "unit_price": 2.30,
                "moq": 50,
                "lead_time_days": 20,
            }
        ]


class GlobalSourcesProvider(SourcingProvider):
    """GlobalSources.com integration provider."""

    async def search_suppliers(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        return [
            {
                "provider": ProviderType.GLOBAL_SOURCES,
                "supplier_id": "gs_supplier_001",
                "name": f"GS Supplier for '{query}'",
                "rating": 4.6,
                "response_time": "< 36h",
                "min_order": 200,
            }
        ]

    async def get_supplier_detail(self, supplier_id: str) -> Dict[str, Any]:
        return {
            "provider": ProviderType.GLOBAL_SOURCES,
            "supplier_id": supplier_id,
            "name": "Sample GS Supplier",
            "verified": True,
            "years_in_business": 12,
            "location": "Dongguan, China",
        }

    async def get_product_quotes(self, product_query: str, quantity: int) -> List[Dict[str, Any]]:
        return [
            {
                "provider": ProviderType.GLOBAL_SOURCES,
                "product": product_query,
                "unit_price": 2.80,
                "moq": 200,
                "lead_time_days": 12,
            }
        ]


# Provider registry
_PROVIDERS: Dict[ProviderType, SourcingProvider] = {
    ProviderType.ALIBABA: AlibabaProvider(),
    ProviderType.MADE_IN_CHINA: MadeInChinaProvider(),
    ProviderType.GLOBAL_SOURCES: GlobalSourcesProvider(),
}


def get_provider(provider_type: ProviderType) -> SourcingProvider:
    """Resolve a provider by type."""
    provider = _PROVIDERS.get(provider_type)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider_type}",
        )
    return provider


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SupplierSearchRequest(BaseModel):
    """Request schema for searching suppliers."""

    query: str = Field(..., min_length=1, max_length=200)
    providers: List[ProviderType] = Field(
        default_factory=lambda: [ProviderType.ALIBABA, ProviderType.MADE_IN_CHINA]
    )
    min_rating: Optional[float] = Field(None, ge=0, le=5)


class QuoteRequest(BaseModel):
    """Request schema for getting quotes."""

    product_query: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=1)
    providers: List[ProviderType] = Field(
        default_factory=lambda: [
            ProviderType.ALIBABA,
            ProviderType.MADE_IN_CHINA,
            ProviderType.GLOBAL_SOURCES,
        ]
    )


class SupplierSaveRequest(BaseModel):
    """Schema for saving a supplier to the user's list."""

    provider: ProviderType
    supplier_id: str
    name: str
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/search")
async def search_suppliers(
    payload: SupplierSearchRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Search suppliers across multiple providers concurrently."""
    import asyncio

    tasks = [
        get_provider(p).search_suppliers(payload.query)
        for p in payload.providers
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_suppliers: List[Dict[str, Any]] = []
    errors: List[str] = []
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            errors.append(f"{payload.providers[idx]}: {str(res)}")
        else:
            all_suppliers.extend(res)

    # Apply optional rating filter
    if payload.min_rating is not None:
        all_suppliers = [s for s in all_suppliers if s.get("rating", 0) >= payload.min_rating]

    return {
        "suppliers": all_suppliers,
        "total": len(all_suppliers),
        "errors": errors,
    }


@router.get("/supplier/{provider}/{supplier_id}")
async def get_supplier_detail(
    provider: ProviderType,
    supplier_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get detailed info for a specific supplier from a provider."""
    p = get_provider(provider)
    return await p.get_supplier_detail(supplier_id)


@router.post("/quotes")
async def get_quotes(
    payload: QuoteRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Get price quotes from multiple providers."""
    import asyncio

    tasks = [
        get_provider(p).get_product_quotes(payload.product_query, payload.quantity)
        for p in payload.providers
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_quotes: List[Dict[str, Any]] = []
    errors: List[str] = []
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            errors.append(f"{payload.providers[idx]}: {str(res)}")
        else:
            all_quotes.extend(res)

    # Sort by unit price ascending
    all_quotes.sort(key=lambda q: q.get("unit_price", float("inf")))

    return {
        "quotes": all_quotes,
        "total": len(all_quotes),
        "errors": errors,
    }


@router.post("/suppliers/save", status_code=status.HTTP_201_CREATED)
async def save_supplier(
    payload: SupplierSaveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Save a supplier to the user's sourcing list."""
    from sqlalchemy import text

    query = text(
        """
        INSERT INTO saved_suppliers (owner_id, provider, supplier_id, name, notes, tags)
        VALUES (:owner_id, :provider, :supplier_id, :name, :notes, :tags)
        ON CONFLICT (owner_id, provider, supplier_id) DO UPDATE
            SET name = EXCLUDED.name, notes = EXCLUDED.notes, tags = EXCLUDED.tags, updated_at = NOW()
        RETURNING *
        """
    )
    result = await db.execute(
        query,
        {
            "owner_id": user_id,
            "provider": payload.provider.value,
            "supplier_id": payload.supplier_id,
            "name": payload.name,
            "notes": payload.notes,
            "tags": payload.tags,
        },
    )
    return dict(result.mappings().first())


@router.get("/suppliers/saved")
async def list_saved_suppliers(
    provider: Optional[ProviderType] = None,
    db: AsyncSession = Depends(get_read_db),
    user_id: str = Depends(get_current_user_id),
):
    """List user's saved suppliers, optionally filtered by provider."""
    from sqlalchemy import text

    conditions = ["owner_id = :owner_id"]
    params: dict = {"owner_id": user_id}
    if provider:
        conditions.append("provider = :provider")
        params["provider"] = provider.value

    where_clause = " AND ".join(conditions)
    query = text(f"SELECT * FROM saved_suppliers WHERE {where_clause} ORDER BY updated_at DESC")
    rows = (await db.execute(query, params)).mappings().all()
    return {"suppliers": [dict(r) for r in rows], "total": len(rows)}
