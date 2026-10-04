from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Deployment, Severity, Source, WebhookEvent, now
from app.schemas.models import IncidentCreate
from app.services.incidents import IncidentService
from app.services.slack import enqueue_incident_notification


def parse_github_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def process_workflow_run(db: Session, webhook_id: str, payload: dict[str, Any]) -> None:
    event = db.scalar(select(WebhookEvent).where(WebhookEvent.provider == "github", WebhookEvent.external_event_id == webhook_id))
    if not event or event.status == "processed":
        return
    run = payload.get("workflow_run", {})
    if not run.get("id"):
        event.status = "failed"
        event.error_message = "Missing workflow_run.id"
        db.commit()
        return
    conclusion = run.get("conclusion")
    deployment_status = "running" if run.get("status") != "completed" else (conclusion or "cancelled")
    repo = payload.get("repository", {}).get("full_name", "unknown")
    deployment = db.scalar(select(Deployment).where(Deployment.github_run_id == str(run["id"])))
    already_failed = bool(deployment and deployment.status == "failure")
    if not deployment:
        deployment = Deployment(
            repository=repo,
            branch=run.get("head_branch", "unknown"),
            commit_sha=run.get("head_sha", "unknown"),
            commit_message=run.get("head_commit", {}).get("message"),
            environment="production",
            status=deployment_status,
            workflow_name=run.get("name"),
            github_run_id=str(run["id"]),
            started_at=parse_github_time(run.get("run_started_at")),
            completed_at=parse_github_time(run.get("updated_at")) if run.get("status") == "completed" else None,
        )
        db.add(deployment)
    else:
        deployment.status = deployment_status
        deployment.completed_at = parse_github_time(run.get("updated_at")) if run.get("status") == "completed" else None
    db.flush()
    if (
        conclusion == "failure"
        and not already_failed
        and get_settings().auto_incident_on_deploy_failure
    ):
        incident = IncidentService(db).create(IncidentCreate(
            title=f"Deployment failed: {repo}",
            description=f"GitHub Actions workflow {run.get('name', 'unknown')} failed on {run.get('head_branch', 'unknown')}",
            environment="production",
            severity=Severity.high,
            source=Source.github,
            metadata={"github_run_id": str(run["id"]), "repository": repo, "commit_sha": run.get("head_sha"), "workflow_url": run.get("html_url")},
        ), event_type="deployment_detected")
        enqueue_incident_notification(str(incident.id))
    event.status = "processed"
    event.processed_at = now()
    db.commit()
