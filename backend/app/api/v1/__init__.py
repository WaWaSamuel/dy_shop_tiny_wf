"""V1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.ecommerce import ecommerce_router
from app.api.v1.feishu import router as feishu_router
from app.api.v1.news import router as news_router

v1_router = APIRouter()
v1_router.include_router(ecommerce_router, prefix="/ecommerce", tags=["ecommerce"])
v1_router.include_router(feishu_router, prefix="/feishu", tags=["feishu"])
v1_router.include_router(news_router, prefix="/news", tags=["news"])
