from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("opspilot", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "monitor-services": {
            "task": "app.workers.tasks.monitor_all_services",
            "schedule": settings.monitor_interval,
        }
    },
)
