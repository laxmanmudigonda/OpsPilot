import httpx
from sqlalchemy import select

from app.db.models import Incident, IncidentEvent, Service, ServiceStatus
from app.services.monitoring import check_service


def test_service_creation(client, headers):
    response = client.post("/api/services", headers=headers, json={
        "name": "Payment API", "slug": "payment-api", "health_check_url": "http://demo-service:8080/health"
    })
    assert response.status_code == 201, response.text
    assert response.json()["current_status"] == "unknown"
    assert client.post("/api/services", headers=headers, json={
        "name": "Duplicate", "slug": "payment-api", "health_check_url": "http://demo-service:8080/health"
    }).status_code == 409


def test_health_transitions_create_one_incident_and_recovery_event(db, monkeypatch):
    service = Service(name="Payment", slug="payment", health_check_url="http://demo/health", current_status=ServiceStatus.healthy)
    db.add(service)
    db.commit()
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: httpx.Response(500))
    assert check_service(db, service.id) == ServiceStatus.down
    assert check_service(db, service.id) == ServiceStatus.down
    assert len(list(db.scalars(select(Incident)))) == 1
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: httpx.Response(200))
    assert check_service(db, service.id) == ServiceStatus.healthy
    event_types = list(db.scalars(select(IncidentEvent.event_type)))
    assert "service_recovered" in event_types


def test_monitor_timeout_becomes_down(db, monkeypatch):
    service = Service(name="Auth", slug="auth", health_check_url="http://demo/health", current_status=ServiceStatus.healthy)
    db.add(service)
    db.commit()
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(httpx, "get", timeout)
    assert check_service(db, service.id) == ServiceStatus.down
