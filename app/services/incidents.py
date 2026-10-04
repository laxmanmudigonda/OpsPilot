from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Incident, IncidentEvent, IncidentStatus, User
from app.repositories.incidents import IncidentRepository
from app.schemas.models import ActorRequest, IncidentCreate

TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.open: {IncidentStatus.acknowledged, IncidentStatus.investigating, IncidentStatus.resolved},
    IncidentStatus.acknowledged: {IncidentStatus.investigating, IncidentStatus.monitoring, IncidentStatus.resolved},
    IncidentStatus.investigating: {IncidentStatus.monitoring, IncidentStatus.resolved},
    IncidentStatus.monitoring: {IncidentStatus.investigating, IncidentStatus.resolved},
    IncidentStatus.resolved: set(),
}


class IncidentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = IncidentRepository(db)

    def create(self, data: IncidentCreate, event_type: str = "incident_created") -> Incident:
        incident = Incident(
            incident_number=self.repo.next_number(),
            title=data.title,
            description=data.description,
            service_id=data.service_id,
            environment=data.environment,
            severity=data.severity,
            source=data.source,
            metadata_=data.metadata,
        )
        self.db.add(incident)
        self.db.flush()
        self._event(incident, event_type, f"Incident {incident.incident_number} created", metadata=data.metadata)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Concurrent incident creation conflict") from None
        self.db.refresh(incident)
        return incident

    def actor(self, data: ActorRequest) -> User:
        user = self.db.scalar(select(User).where(User.slack_user_id == data.slack_user_id))
        if not user:
            user = User(
                slack_user_id=data.slack_user_id,
                slack_username=data.slack_username,
                display_name=data.display_name,
            )
            self.db.add(user)
            self.db.flush()
        return user

    def acknowledge(self, incident_id: UUID, actor_data: ActorRequest) -> Incident:
        incident = self._locked(incident_id)
        actor = self.actor(actor_data)
        if incident.status == IncidentStatus.resolved:
            raise HTTPException(status_code=409, detail="Resolved incidents cannot be acknowledged")
        if incident.acknowledged_at:
            self.db.commit()
            return incident
        incident.acknowledged_by = actor.id
        incident.acknowledged_at = datetime.now(UTC)
        if incident.status == IncidentStatus.open:
            incident.status = IncidentStatus.acknowledged
        self._event(incident, "acknowledged", f"Acknowledged by {actor.display_name or actor.slack_user_id}", actor.id)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def assign(self, incident_id: UUID, actor_data: ActorRequest) -> Incident:
        incident = self._locked(incident_id)
        if incident.status == IncidentStatus.resolved:
            raise HTTPException(status_code=409, detail="Resolved incidents cannot be assigned")
        actor = self.actor(actor_data)
        if incident.assigned_to != actor.id:
            incident.assigned_to = actor.id
            self._event(incident, "assigned", f"Assigned to {actor.display_name or actor.slack_user_id}", actor.id)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def transition(self, incident_id: UUID, new_status: IncidentStatus, actor_data: ActorRequest | None = None, message: str | None = None) -> Incident:
        incident = self._locked(incident_id)
        if incident.status == new_status:
            self.db.commit()
            return incident
        if new_status not in TRANSITIONS[incident.status]:
            raise HTTPException(status_code=409, detail=f"Invalid transition: {incident.status.value} -> {new_status.value}")
        actor = self.actor(actor_data) if actor_data else None
        old = incident.status
        incident.status = new_status
        if new_status == IncidentStatus.acknowledged and not incident.acknowledged_at:
            incident.acknowledged_at = datetime.now(UTC)
            incident.acknowledged_by = actor.id if actor else None
        if new_status == IncidentStatus.resolved:
            incident.resolved_at = datetime.now(UTC)
        event_type = "resolved" if new_status == IncidentStatus.resolved else "status_changed"
        self._event(incident, event_type, message or f"Status changed from {old.value} to {new_status.value}", actor.id if actor else None)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def _locked(self, incident_id: UUID) -> Incident:
        incident = self.repo.get(incident_id, for_update=True)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        return incident

    def _event(self, incident: Incident, event_type: str, message: str, actor_id: UUID | None = None, metadata: dict | None = None) -> None:
        self.db.add(IncidentEvent(incident_id=incident.id, event_type=event_type, message=message, actor_id=actor_id, metadata_=metadata or {}))
