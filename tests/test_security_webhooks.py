import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from sqlalchemy import func, select

from app.core.security import verify_hmac, verify_slack_request
from app.db.models import Incident, Service, WebhookEvent
from app.services.github import process_workflow_run


def test_signatures():
    body = b'{"hello":"world"}'
    github = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_hmac("secret", body, github)
    assert not verify_hmac("wrong", body, github)
    timestamp = str(int(time.time()))
    base = f"v0:{timestamp}:".encode() + body
    slack = "v0=" + hmac.new(b"secret", base, hashlib.sha256).hexdigest()
    assert verify_slack_request("secret", body, timestamp, slack)
    assert not verify_slack_request("secret", body, "1", slack)


def test_github_webhook_and_duplicate(client, monkeypatch):
    body = json.dumps({"workflow_run": {"id": 42, "status": "completed", "conclusion": "success"}}).encode()
    signature = "sha256=" + hmac.new(b"github-test-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": signature, "X-GitHub-Delivery": "delivery-1", "X-GitHub-Event": "workflow_run"}
    monkeypatch.setattr("app.api.routes.webhooks.process_github_event.delay", lambda *args: None)
    first = client.post("/webhooks/github", content=body, headers=headers)
    assert first.status_code == 202
    assert first.json()["status"] == "accepted"
    second = client.post("/webhooks/github", content=body, headers=headers)
    assert second.json()["status"] == "duplicate"


def test_invalid_webhook_signatures(client):
    assert client.post("/webhooks/github", content=b"{}", headers={"X-Hub-Signature-256": "sha256=no"}).status_code == 401
    assert client.post("/webhooks/slack", content=b"command=x", headers={"X-Slack-Signature": "v0=no", "X-Slack-Request-Timestamp": str(int(time.time()))}).status_code == 401


def test_health_and_api_auth(client):
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/api/incidents").status_code == 401


def test_failed_workflow_creates_only_one_incident(db):
    payload = {
        "repository": {"full_name": "example/backend"},
        "workflow_run": {
            "id": 99,
            "status": "completed",
            "conclusion": "failure",
            "name": "Deploy Production",
            "head_branch": "main",
            "head_sha": "abc123",
        },
    }
    for delivery in ("failure-1", "failure-2"):
        db.add(
            WebhookEvent(
                provider="github",
                external_event_id=delivery,
                event_type="workflow_run",
                payload_hash="hash",
            )
        )
        db.commit()
        process_workflow_run(db, delivery, payload)
    assert db.scalar(select(func.count()).select_from(Incident)) == 1


def slack_headers(body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    base = f"v0:{timestamp}:".encode() + body
    signature = "v0=" + hmac.new(b"slack-test-secret", base, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
    }


def test_slack_command_creates_and_queues_incident(client, db, monkeypatch):
    service = Service(
        name="Payment API",
        slug="payment-api",
        health_check_url="http://demo-service:8080/health",
    )
    db.add(service)
    db.commit()
    queued: list[str] = []
    monkeypatch.setattr(
        "app.api.routes.webhooks.enqueue_incident_notification", queued.append
    )
    body = urlencode(
        {
            "command": "/incident",
            "text": "create payment-api Checkout requests are failing",
            "user_id": "U123",
        }
    ).encode()
    response = client.post("/webhooks/slack", content=body, headers=slack_headers(body))
    assert response.status_code == 200
    assert "INC-" in response.json()["text"]
    assert len(queued) == 1


def test_slack_action_returns_updated_card(client, headers):
    created = client.post(
        "/api/incidents",
        headers=headers,
        json={"title": "API down", "description": "Health check failed"},
    ).json()
    payload = {
        "user": {"id": "U123", "name": "Responder"},
        "actions": [{"action_id": "incident_ack", "value": created["id"]}],
    }
    body = urlencode({"payload": json.dumps(payload)}).encode()
    response = client.post("/webhooks/slack", content=body, headers=slack_headers(body))
    assert response.status_code == 200
    assert response.json()["replace_original"] is True
    fields = response.json()["blocks"][1]["fields"]
    assert any("Acknowledged" in field["text"] for field in fields)
