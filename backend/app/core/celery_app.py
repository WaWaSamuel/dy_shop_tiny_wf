"""Celery application configuration with Redis broker.

Workers process background tasks such as product uploads, image generation,
and data synchronization jobs.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "douyin_shop_automation",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Asia/Shanghai",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result expiration (24 hours)
    result_expires=86400,

    # Task routing
    task_routes={
        "app.tasks.product_upload.*": {"queue": "product_upload"},
        "app.tasks.discovery.*": {"queue": "discovery"},
        "app.tasks.design_assets.*": {"queue": "design_assets"},
        "app.tasks.feedback.*": {"queue": "feedback"},
    },

    # Retry policy
    task_default_retry_delay=30,
    task_max_retries=3,

    # Worker concurrency
    worker_concurrency=4,
)

# Auto-discover tasks from the app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])
