"""Main API router that aggregates all module routers.

Includes all module routers under the /api/v1/ prefix:
- /api/v1/feedback/* - Customer feedback management
- /api/v1/products/* - Product upload and listing
- /api/v1/discovery/* - Product discovery and sourcing
- /api/v1/design/* - Design asset generation
- /api/v1/system/* - System health, metrics, and reports
"""

from fastapi import APIRouter

from app.api.system import system_router

api_router = APIRouter(prefix="/api/v1")


def setup_routers() -> APIRouter:
    """Configure and return the main API router with all sub-routers.

    Call this during app startup to register all module routes.

    Returns:
        Configured APIRouter with all module routes included.
    """
    # Import module routers
    from app.modules.feedback.router import router as feedback_router
    from app.modules.product_upload.router import router as product_upload_router
    from app.modules.discovery.router import router as discovery_router
    from app.modules.design_assets.router import router as design_assets_router

    # Include module routers
    api_router.include_router(
        feedback_router,
        prefix="/feedback",
        tags=["Feedback"],
    )
    api_router.include_router(
        product_upload_router,
        prefix="/products",
        tags=["Product Upload"],
    )
    api_router.include_router(
        discovery_router,
        prefix="/discovery",
        tags=["Discovery"],
    )
    api_router.include_router(
        design_assets_router,
        prefix="/design",
        tags=["Design Assets"],
    )

    # Include system router
    api_router.include_router(
        system_router,
        prefix="/system",
        tags=["System"],
    )

    return api_router
