"""Run the complete REST-based demo after `docker compose up --build`."""
import os
import time

import httpx

API = os.getenv("OPSPILOT_URL", "http://localhost:18000")
DEMO = os.getenv("DEMO_SERVICE_URL", "http://localhost:18080")
HEADERS = {"X-API-Key": os.getenv("API_KEY", "change-me-to-a-long-random-value")}


def main() -> None:
    with httpx.Client(timeout=10) as client:
        print("API:", client.get(f"{API}/health").json())
        services = client.get(f"{API}/api/services", headers=HEADERS).json()
        service = next((item for item in services if item["slug"] == "demo-payment-api"), None)
        if not service:
            response = client.post(f"{API}/api/services", headers=HEADERS, json={
                "name": "Demo Payment API", "slug": "demo-payment-api",
                "health_check_url": "http://demo-service:8080/health", "health_check_interval": 5,
            })
            response.raise_for_status()
            service = response.json()
        print("Registered:", service["name"])
        client.post(f"{DEMO}/recover").raise_for_status()
        print("Demo service healthy. Triggering failure...")
        client.post(f"{DEMO}/fail").raise_for_status()
        incident = None
        for _ in range(12):
            time.sleep(5)
            items = client.get(
                f"{API}/api/incidents?service_id={service['id']}&status=open",
                headers=HEADERS,
            ).json()["items"]
            if items:
                incident = items[0]
                break
            print("Waiting for scheduled monitor...")
        if not incident:
            raise RuntimeError("No incident detected within 60 seconds")
        incident_id = incident["id"]
        actor = {"slack_user_id": "U-DEMO", "display_name": "Demo Responder"}
        print("Detected:", incident["incident_number"])
        client.post(f"{API}/api/incidents/{incident_id}/acknowledge", headers=HEADERS, json=actor).raise_for_status()
        client.post(f"{API}/api/incidents/{incident_id}/assign", headers=HEADERS, json=actor).raise_for_status()
        client.post(f"{DEMO}/recover").raise_for_status()
        print("Recovered service; waiting for recovery check...")
        for _ in range(12):
            time.sleep(5)
            current = client.get(
                f"{API}/api/services/{service['id']}", headers=HEADERS
            ).json()["current_status"]
            if current == "healthy":
                break
        else:
            raise RuntimeError("Recovery was not detected within 60 seconds")
        client.post(f"{API}/api/incidents/{incident_id}/resolve", headers=HEADERS, json=actor).raise_for_status()
        timeline = client.get(f"{API}/api/incidents/{incident_id}/timeline", headers=HEADERS).json()
        summary = client.post(f"{API}/api/incidents/{incident_id}/summary", headers=HEADERS).json()
        print("Timeline:")
        for event in timeline:
            print(f"  {event['created_at']}  {event['event_type']}: {event['message']}")
        print("Summary:", summary["content"])


if __name__ == "__main__":
    main()
