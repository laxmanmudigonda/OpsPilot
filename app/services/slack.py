import logging
from typing import Any

from slack_sdk import WebClient

from app.core.config import get_settings
from app.db.models import Incident

logger = logging.getLogger(__name__)


def incident_blocks(incident: Incident) -> list[dict[str, Any]]:
    service = incident.service.name if incident.service else "Unspecified service"
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": "🚨 Production Incident"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Incident*\n{incident.incident_number}"},
            {"type": "mrkdwn", "text": f"*Service*\n{service}"},
            {"type": "mrkdwn", "text": f"*Severity*\n{incident.severity.value.title()}"},
            {"type": "mrkdwn", "text": f"*Status*\n{incident.status.value.title()}"},
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": incident.description}},
    ]
    if incident.status.value != "resolved":
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Acknowledge"}, "action_id": "incident_ack", "value": str(incident.id)},
            {"type": "button", "text": {"type": "plain_text", "text": "Assign to Me"}, "action_id": "incident_assign", "value": str(incident.id)},
            {"type": "button", "text": {"type": "plain_text", "text": "Investigating"}, "action_id": "incident_investigate", "value": str(incident.id)},
            {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Resolve"}, "action_id": "incident_resolve", "value": str(incident.id)},
        ]})
    else:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "✅ Resolved — actions are now closed."}],
        })
    return blocks


def notify_incident(incident: Incident) -> None:
    settings = get_settings()
    if not settings.slack_bot_token or not settings.slack_incident_channel_id:
        return
    WebClient(token=settings.slack_bot_token).chat_postMessage(
        channel=settings.slack_incident_channel_id,
        text=f"Incident {incident.incident_number}: {incident.title}",
        blocks=incident_blocks(incident),
    )


def enqueue_incident_notification(incident_id: str) -> None:
    """Queue Slack delivery only when Slack is configured; never undo a committed incident."""
    if not get_settings().slack_bot_token:
        return
    try:
        from app.workers.tasks import send_incident_notification

        send_incident_notification.delay(incident_id)
    except Exception as exc:
        logger.warning("Could not enqueue Slack notification: %s", exc)
