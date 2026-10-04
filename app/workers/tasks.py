import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models import Incident, Service
from app.db.session import SessionLocal
from app.services.github import process_workflow_run
from app.services.monitoring import acquire_monitor_lock, check_service
from app.services.slack import notify_incident
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, autoretry_for=(ConnectionError, TimeoutError), retry_backoff=True, retry_jitter=True, max_retries=4)
def process_github_event(self, delivery_id: str, payload: dict) -> None:
    with SessionLocal() as db:
        process_workflow_run(db, delivery_id, payload)


@celery_app.task(bind=True, autoretry_for=(ConnectionError, TimeoutError), retry_backoff=True, retry_jitter=True, max_retries=3)
def monitor_service(self, service_id: str) -> None:
    redis_client = Redis.from_url(get_settings().redis_url)
    try:
        if not acquire_monitor_lock(redis_client, UUID(service_id)):
            return
        with SessionLocal() as db:
            check_service(db, UUID(service_id))
    finally:
        redis_client.close()


@celery_app.task
def monitor_all_services() -> int:
    with SessionLocal() as db:
        current = datetime.now(UTC)
        services = list(db.scalars(select(Service)))
        ids = [
            service.id
            for service in services
            if service.last_checked_at is None
            or current - service.last_checked_at >= timedelta(seconds=service.health_check_interval)
        ]
    for service_id in ids:
        monitor_service.delay(str(service_id))
    return len(ids)


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=4,
)
def send_incident_notification(self, incident_id: str) -> None:
    with SessionLocal() as db:
        incident = db.scalar(
            select(Incident)
            .options(selectinload(Incident.service))
            .where(Incident.id == UUID(incident_id))
        )
        if incident:
            notify_incident(incident)
