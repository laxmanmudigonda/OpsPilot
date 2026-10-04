import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    Incident,
    IncidentEvent,
    IncidentStatus,
    Service,
    ServiceStatus,
    Severity,
    Source,
)
from app.schemas.models import IncidentCreate
from app.services.incidents import IncidentService
from app.services.slack import enqueue_incident_notification

logger = logging.getLogger(__name__)


def check_service(db: Session, service_id: UUID) -> ServiceStatus:
    service = db.get(Service, service_id)
    if not service:
        raise ValueError("Service not found")
    settings = get_settings()
    previous = service.current_status
    try:
        response = httpx.get(service.health_check_url, timeout=settings.monitor_timeout, follow_redirects=False)
        current = ServiceStatus.healthy if response.status_code == service.expected_status_code else ServiceStatus.down
    except httpx.HTTPError as exc:
        logger.warning("Health check failed: %s", exc, extra={"error_type": type(exc).__name__})
        current = ServiceStatus.down
    service.current_status = current
    service.last_checked_at = datetime.now(UTC)
    if current != previous:
        _handle_transition(db, service, previous, current)
    db.commit()
    return current


def _handle_transition(db: Session, service: Service, previous: ServiceStatus, current: ServiceStatus) -> None:
    if current == ServiceStatus.down:
        active = db.scalar(
            select(Incident).where(
                Incident.service_id == service.id,
                Incident.source == Source.monitoring,
                Incident.status != IncidentStatus.resolved,
            )
        )
        if not active:
            incident = IncidentService(db).create(IncidentCreate(
                title=f"{service.name} health check failed",
                description=f"Expected HTTP {service.expected_status_code} from {service.health_check_url}",
                service_id=service.id,
                environment=service.environment,
                severity=Severity.high,
                source=Source.monitoring,
                metadata={"previous_status": previous.value},
            ))
            logger.error("Monitoring incident created", extra={"incident_id": str(incident.id)})
            enqueue_incident_notification(str(incident.id))
    elif current == ServiceStatus.healthy and previous == ServiceStatus.down:
        incident = db.scalar(
            select(Incident).where(
                Incident.service_id == service.id,
                Incident.source == Source.monitoring,
                Incident.status != IncidentStatus.resolved,
            ).order_by(Incident.created_at.desc())
        )
        if incident:
            db.add(IncidentEvent(
                incident_id=incident.id,
                event_type="service_recovered",
                message=f"{service.name} health check recovered; incident remains open for review",
                metadata_={"current_status": current.value},
            ))


def acquire_monitor_lock(redis_client: Redis, service_id: UUID, ttl: int = 30) -> bool:
    return bool(redis_client.set(f"monitor-lock:{service_id}", "1", nx=True, ex=ttl))
