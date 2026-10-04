from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import Incident, IncidentStatus, Severity


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, incident_id: UUID, *, for_update: bool = False) -> Incident | None:
        query = select(Incident).where(Incident.id == incident_id)
        if for_update:
            query = query.with_for_update()
        return self.db.scalar(query)

    def list_query(
        self, status: IncidentStatus | None, severity: Severity | None, service_id: UUID | None
    ) -> Select[tuple[Incident]]:
        query = select(Incident)
        if status:
            query = query.where(Incident.status == status)
        if severity:
            query = query.where(Incident.severity == severity)
        if service_id:
            query = query.where(Incident.service_id == service_id)
        return query

    def next_number(self) -> str:
        maximum = self.db.scalar(select(func.count()).select_from(Incident)) or 0
        return f"INC-{maximum + 1001:04d}"
