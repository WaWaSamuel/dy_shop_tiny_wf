"""FastAPI application entry point for Douyin Shop Automation.

Configures CORS, includes API routers, and manages application lifecycle events.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    CircuitBreakerOpen,
    DouyinAPIError,
    RateLimitExceeded,
    ValidationError,
)
from app.core.redis import close_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    # Startup: nothing extra needed (lazy initialization for DB/Redis)
    yield
    # Shutdown: clean up connection pools
    await close_redis_pool()


app = FastAPI(
    title="Douyin Shop Automation",
    description="Backend API for automated Douyin Shop product management, "
    "discovery, feedback analysis, and design asset generation.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception Handlers ---


@app.exception_handler(DouyinAPIError)
async def douyin_api_error_handler(request: Request, exc: DouyinAPIError) -> JSONResponse:
    """Handle Douyin API errors with structured response."""
    return JSONResponse(
        status_code=exc.status_code or 502,
        content={
            "error": "douyin_api_error",
            "message": exc.message,
            "detail": exc.response_body,
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": str(exc),
            "retry_after": exc.retry_after,
        },
        headers={"Retry-After": str(int(exc.retry_after))},
    )


@app.exception_handler(CircuitBreakerOpen)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerOpen) -> JSONResponse:
    """Handle circuit breaker open errors."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "service_unavailable",
            "message": str(exc),
            "retry_after": exc.retry_after,
        },
        headers={"Retry-After": str(int(exc.retry_after))},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle domain validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "field": exc.field,
            "message": exc.detail,
        },
    )


# --- Routers ---
# Import and include routers for each domain module.
from app.routers import feedback, product_upload, discovery, design_assets  # noqa: E402

app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(product_upload.router, prefix="/api/v1/products", tags=["Product Upload"])
app.include_router(discovery.router, prefix="/api/v1/discovery", tags=["Discovery"])
app.include_router(design_assets.router, prefix="/api/v1/design", tags=["Design Assets"])


# --- Health Check ---


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "douyin-shop-automation"}
