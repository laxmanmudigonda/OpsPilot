def create_incident(client, headers):
    response = client.post("/api/incidents", headers=headers, json={
        "title": "Payment API unavailable", "description": "HTTP 500 rate exceeded threshold",
        "severity": "high", "source": "api",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_incident_lifecycle_and_timeline(client, headers):
    incident = create_incident(client, headers)
    actor = {"slack_user_id": "U123", "display_name": "Laxman"}
    ack = client.post(f"/api/incidents/{incident['id']}/acknowledge", headers=headers, json=actor)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    duplicate = client.post(f"/api/incidents/{incident['id']}/acknowledge", headers=headers, json=actor)
    assert duplicate.status_code == 200
    assigned = client.post(f"/api/incidents/{incident['id']}/assign", headers=headers, json=actor)
    assert assigned.json()["assigned_to"]
    investigating = client.patch(f"/api/incidents/{incident['id']}/status", headers=headers, json={"status": "investigating", "actor": actor})
    assert investigating.json()["status"] == "investigating"
    resolved = client.post(f"/api/incidents/{incident['id']}/resolve", headers=headers, json=actor)
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"]
    timeline = client.get(f"/api/incidents/{incident['id']}/timeline", headers=headers).json()
    assert [event["event_type"] for event in timeline] == ["incident_created", "acknowledged", "assigned", "status_changed", "resolved"]


def test_invalid_transition_and_pagination(client, headers):
    incident = create_incident(client, headers)
    client.post(f"/api/incidents/{incident['id']}/resolve", headers=headers)
    response = client.patch(f"/api/incidents/{incident['id']}/status", headers=headers, json={"status": "acknowledged"})
    assert response.status_code == 409
    listing = client.get("/api/incidents?status=resolved&page=1&page_size=10", headers=headers)
    assert listing.json()["total"] == 1


def test_summary_requires_and_reuses_generated_report(client, headers):
    incident = create_incident(client, headers)
    missing = client.get(f"/api/incidents/{incident['id']}/summary", headers=headers)
    assert missing.status_code == 404
    generated = client.post(f"/api/incidents/{incident['id']}/summary", headers=headers)
    assert generated.status_code == 200
    assert generated.json()["content"]["incident"].startswith("INC-")
    assert client.post(f"/api/incidents/{incident['id']}/summary", headers=headers).json() == generated.json()
