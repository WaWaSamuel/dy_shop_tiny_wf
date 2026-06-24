"""API package for Douyin Shop Automation.

Provides the main API router that aggregates all module routers
under the /api/v1/ prefix, plus system management endpoints.
"""

from app.api.router import api_router
from app.api.system import system_router

__all__ = [
    "api_router",
    "system_router",
]
