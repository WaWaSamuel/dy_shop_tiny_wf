"""Ecommerce module router aggregation."""

from fastapi import APIRouter

from app.api.v1.ecommerce.analytics import router as analytics_router
from app.api.v1.ecommerce.creative import router as creative_router
from app.api.v1.ecommerce.flow import router as flow_router
from app.api.v1.ecommerce.orders import router as orders_router
from app.api.v1.ecommerce.products import router as products_router
from app.api.v1.ecommerce.results import router as results_router
from app.api.v1.ecommerce.sourcing import router as sourcing_router

ecommerce_router = APIRouter()

ecommerce_router.include_router(products_router, prefix="/products", tags=["products"])
ecommerce_router.include_router(orders_router, prefix="/orders", tags=["orders"])
ecommerce_router.include_router(results_router, prefix="/results", tags=["results"])
ecommerce_router.include_router(sourcing_router, prefix="/sourcing", tags=["sourcing"])
ecommerce_router.include_router(creative_router, prefix="/creative", tags=["creative"])
ecommerce_router.include_router(flow_router, prefix="/flow", tags=["flow"])
ecommerce_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
