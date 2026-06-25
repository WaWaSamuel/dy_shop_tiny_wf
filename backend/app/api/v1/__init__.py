"""V1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.ecommerce import ecommerce_router

v1_router = APIRouter()
v1_router.include_router(ecommerce_router, prefix="/ecommerce", tags=["ecommerce"])
