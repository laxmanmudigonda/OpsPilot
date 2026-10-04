from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Incident, IncidentSummary


def generate_summary(db: Session, incident: Incident) -> IncidentSummary:
    existing = db.scalar(select(IncidentSummary).where(IncidentSummary.incident_id == incident.id))
    if existing:
        return existing
    events = sorted(incident.events, key=lambda item: item.created_at)
    duration = None
    if incident.resolved_at:
        duration = max(0, int((incident.resolved_at - incident.detected_at).total_seconds() / 60))
    content = {
        "incident": incident.incident_number,
        "what_happened": incident.description,
        "impact": f"{incident.severity.value.title()} severity impact to {incident.environment}.",
        "duration_minutes": duration,
        "timeline": [{"at": event.created_at.isoformat(), "event": event.event_type, "message": event.message} for event in events],
        "probable_cause": incident.metadata_.get("probable_cause", "Requires human review."),
        "resolution": next((event.message for event in reversed(events) if event.event_type == "resolved"), "Not yet resolved."),
        "preventive_actions": ["Review alerting and deployment safeguards", "Record follow-up actions with owners"],
    }
    summary = IncidentSummary(incident_id=incident.id, content=content)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary
