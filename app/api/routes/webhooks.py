import hashlib
import json
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_hmac, verify_slack_request
from app.db.models import IncidentStatus, Service, Severity, Source, WebhookEvent
from app.db.session import get_db
from app.schemas.models import ActorRequest, IncidentCreate
from app.services.incidents import IncidentService
from app.services.slack import enqueue_incident_notification, incident_blocks
from app.workers.tasks import process_github_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
    x_github_event: str = Header(default=""),
) -> dict[str, str]:
    body = await request.body()
    if not verify_hmac(get_settings().github_webhook_secret, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid GitHub signature")
    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing GitHub delivery ID")
    event = WebhookEvent(
        provider="github", external_event_id=x_github_delivery, event_type=x_github_event,
        payload_hash=hashlib.sha256(body).hexdigest(),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    if x_github_event == "workflow_run":
        process_github_event.delay(x_github_delivery, json.loads(body))
    return {"status": "accepted"}


def slack_actor(payload: dict) -> ActorRequest:
    user = payload.get("user", {})
    return ActorRequest(slack_user_id=user.get("id", "unknown"), slack_username=user.get("username"), display_name=user.get("name"))


@router.post("/slack")
async def slack_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_signature: str = Header(default=""),
) -> dict:
    body = await request.body()
    if not verify_slack_request(get_settings().slack_signing_secret, body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    form = parse_qs(body.decode())
    if "payload" in form:
        payload = json.loads(form["payload"][0])
        action = payload.get("actions", [{}])[0]
        incident_id = UUID(action["value"])
        actor = slack_actor(payload)
        service = IncidentService(db)
        match action.get("action_id"):
            case "incident_ack":
                incident = service.acknowledge(incident_id, actor)
            case "incident_assign":
                incident = service.assign(incident_id, actor)
            case "incident_investigate":
                incident = service.transition(incident_id, IncidentStatus.investigating, actor)
            case "incident_resolve":
                incident = service.transition(incident_id, IncidentStatus.resolved, actor)
            case _:
                raise HTTPException(status_code=400, detail="Unknown Slack action")
        return {
            "replace_original": True,
            "text": f"{incident.incident_number}: {incident.status.value}",
            "blocks": incident_blocks(incident),
        }
    command = form.get("command", [""])[0]
    text = form.get("text", [""])[0].strip()
    user_id = form.get("user_id", ["unknown"])[0]
    if command in {"/incidents", "/incident-list"}:
        from app.db.models import Incident
        incidents = list(db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(10)))
        return {"response_type": "ephemeral", "text": "\n".join(f"{i.incident_number} · {i.status.value} · {i.title}" for i in incidents) or "No incidents."}
    if command in {"/service-status", "/service-list"}:
        services = list(db.scalars(select(Service).order_by(Service.name)))
        return {"response_type": "ephemeral", "text": "\n".join(f"{s.name}: {s.current_status.value}" for s in services) or "No services."}
    if command in {"/incident", "/incident-create"}:
        parts = text.removeprefix("create ").split(maxsplit=1)
        if len(parts) != 2:
            return {"response_type": "ephemeral", "text": "Usage: /incident create <service-slug> <description>"}
        registered = db.scalar(select(Service).where(Service.slug == parts[0]))
        if not registered:
            return {"response_type": "ephemeral", "text": f"Unknown service: {parts[0]}"}
        incident = IncidentService(db).create(IncidentCreate(
            title=parts[1][:250], description=parts[1], service_id=registered.id,
            environment=registered.environment, severity=Severity.high, source=Source.manual,
            metadata={"slack_user_id": user_id},
        ))
        enqueue_incident_notification(str(incident.id))
        return {"response_type": "in_channel", "text": f"🚨 {incident.incident_number} created for {registered.name}: {incident.title}"}
    return {"response_type": "ephemeral", "text": "Unsupported command."}
