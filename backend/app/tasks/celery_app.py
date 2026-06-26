"""Celery application configuration."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

# Create Celery application
celery_app = Celery("personal_studio")

# Configuration
celery_app.conf.update(
    # Broker (Redis)
    broker_url="redis://localhost:6379/1",
    result_backend="redis://localhost:6379/2",

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="Asia/Shanghai",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # Task routing
    task_routes={
        "app.tasks.creative_tasks.*": {"queue": "creative"},
        "app.tasks.sync_tasks.*": {"queue": "sync"},
        "app.tasks.notification_tasks.*": {"queue": "notification"},
        "app.tasks.news_tasks.*": {"queue": "sync"},
    },

    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit

    # Result expiration
    result_expires=86400,  # 24 hours

    # Retry configuration
    task_default_retry_delay=60,
    task_max_retries=3,

    # Beat schedule for periodic tasks
    beat_schedule={
        "sync-orders-every-5-minutes": {
            "task": "app.tasks.sync_tasks.sync_platform_orders",
            "schedule": 300.0,  # Every 5 minutes
            "options": {"queue": "sync"},
        },
        "sync-inventory-every-15-minutes": {
            "task": "app.tasks.sync_tasks.sync_inventory",
            "schedule": 900.0,  # Every 15 minutes
            "options": {"queue": "sync"},
        },
        "check-stale-orders-hourly": {
            "task": "app.tasks.sync_tasks.check_stale_orders",
            "schedule": crontab(minute=0),  # Every hour
            "options": {"queue": "sync"},
        },
        "daily-stats-aggregation": {
            "task": "app.tasks.sync_tasks.aggregate_daily_stats",
            "schedule": crontab(hour=2, minute=0),  # 2:00 AM daily
            "options": {"queue": "sync"},
        },
        "refresh-news-digest-daily": {
            "task": "app.tasks.news_tasks.refresh_news_digest",
            "schedule": crontab(hour=9, minute=5),  # 09:05 daily, covers 21:00-09:00 window
            "options": {"queue": "sync"},
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(
    [
        "app.tasks.creative_tasks",
        "app.tasks.sync_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.news_tasks",
    ]
)
