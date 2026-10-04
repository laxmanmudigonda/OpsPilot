from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import require_api_key
from app.db.models import Incident, IncidentEvent, IncidentStatus, IncidentSummary, Severity
from app.db.session import get_db
from app.repositories.incidents import IncidentRepository
from app.schemas.models import (
    ActorRequest,
    IncidentCreate,
    IncidentEventRead,
    IncidentList,
    IncidentRead,
    StatusUpdate,
    SummaryRead,
)
from app.services.incidents import IncidentService
from app.services.slack import enqueue_incident_notification
from app.services.summaries import generate_summary

router = APIRouter(prefix="/api/incidents", tags=["incidents"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(data: IncidentCreate, db: Session = Depends(get_db)) -> Incident:
    incident = IncidentService(db).create(data)
    enqueue_incident_notification(str(incident.id))
    return incident


@router.get("", response_model=IncidentList)
def list_incidents(
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    severity: Severity | None = None,
    service_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> IncidentList:
    repo = IncidentRepository(db)
    filtered = repo.list_query(incident_status, severity, service_id)
    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    ordering = Incident.created_at.asc() if order == "asc" else Incident.created_at.desc()
    items = list(db.scalars(filtered.order_by(ordering).offset((page - 1) * page_size).limit(page_size)))
    return IncidentList(items=items, total=total, page=page, page_size=page_size)


def fetch(incident_id: UUID, db: Session) -> Incident:
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: UUID, db: Session = Depends(get_db)) -> Incident:
    return fetch(incident_id, db)


@router.post("/{incident_id}/acknowledge", response_model=IncidentRead)
def acknowledge(incident_id: UUID, actor: ActorRequest, db: Session = Depends(get_db)) -> Incident:
    return IncidentService(db).acknowledge(incident_id, actor)


@router.post("/{incident_id}/assign", response_model=IncidentRead)
def assign(incident_id: UUID, actor: ActorRequest, db: Session = Depends(get_db)) -> Incident:
    return IncidentService(db).assign(incident_id, actor)


@router.patch("/{incident_id}/status", response_model=IncidentRead)
def update_status(incident_id: UUID, data: StatusUpdate, db: Session = Depends(get_db)) -> Incident:
    return IncidentService(db).transition(incident_id, data.status, data.actor, data.message)


@router.post("/{incident_id}/resolve", response_model=IncidentRead)
def resolve(incident_id: UUID, actor: ActorRequest | None = None, db: Session = Depends(get_db)) -> Incident:
    return IncidentService(db).transition(incident_id, IncidentStatus.resolved, actor)


@router.get("/{incident_id}/timeline", response_model=list[IncidentEventRead])
def timeline(incident_id: UUID, db: Session = Depends(get_db)) -> list[IncidentEvent]:
    fetch(incident_id, db)
    return list(db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.created_at)))


@router.post("/{incident_id}/summary", response_model=SummaryRead)
def create_summary(incident_id: UUID, db: Session = Depends(get_db)) -> SummaryRead:
    incident = db.scalar(select(Incident).options(selectinload(Incident.events)).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    summary = generate_summary(db, incident)
    return SummaryRead(incident_id=incident.id, provider=summary.provider, content=summary.content)


@router.get("/{incident_id}/summary", response_model=SummaryRead)
def get_summary(incident_id: UUID, db: Session = Depends(get_db)) -> SummaryRead:
    summary = db.scalar(select(IncidentSummary).where(IncidentSummary.incident_id == incident_id))
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not generated")
    return SummaryRead(incident_id=incident_id, provider=summary.provider, content=summary.content)
