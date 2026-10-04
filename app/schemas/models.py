from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.db.models import IncidentStatus, ServiceStatus, Severity, Source


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    description: str | None = None
    environment: str = Field(default="production", max_length=50)
    health_check_url: HttpUrl
    expected_status_code: int = Field(default=200, ge=100, le=599)
    health_check_interval: int = Field(default=30, ge=5, le=86400)


class ServiceRead(ORMModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    environment: str
    health_check_url: str
    expected_status_code: int
    health_check_interval: int
    current_status: ServiceStatus
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(min_length=3, max_length=5000)
    service_id: UUID | None = None
    environment: str = Field(default="production", max_length=50)
    severity: Severity = Severity.medium
    source: Source = Source.api
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentRead(ORMModel):
    id: UUID
    incident_number: str
    title: str
    description: str
    service_id: UUID | None
    environment: str
    severity: Severity
    status: IncidentStatus
    source: Source
    acknowledged_by: UUID | None
    assigned_to: UUID | None
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentList(BaseModel):
    items: list[IncidentRead]
    total: int
    page: int
    page_size: int


class ActorRequest(BaseModel):
    slack_user_id: str = Field(min_length=1, max_length=64)
    slack_username: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=200)


class StatusUpdate(BaseModel):
    status: IncidentStatus
    actor: ActorRequest | None = None
    message: str | None = Field(default=None, max_length=1000)


class IncidentEventRead(ORMModel):
    id: UUID
    incident_id: UUID
    event_type: str
    message: str
    actor_id: UUID | None
    metadata_: dict[str, Any]
    created_at: datetime


class SummaryRead(BaseModel):
    incident_id: UUID
    provider: str
    content: dict[str, Any]
