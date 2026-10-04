from app.db.models import Deployment, Service
from app.db.session import SessionLocal
from app.schemas.models import IncidentCreate
from app.services.incidents import IncidentService


def main() -> None:
    with SessionLocal() as db:
        services = [
            Service(name="Demo Payment API", slug="demo-payment-api", description="Payment authorization demo", environment="production", health_check_url="http://demo-service:8080/health", health_check_interval=5),
            Service(name="Demo Authentication Service", slug="demo-auth", description="Authentication demo", environment="staging", health_check_url="http://demo-service:8080/health", health_check_interval=30),
        ]
        for service in services:
            if not db.query(Service).filter_by(slug=service.slug).first():
                db.add(service)
        db.commit()
        payment = db.query(Service).filter_by(slug="demo-payment-api").one()
        if not payment.incidents:
            IncidentService(db).create(IncidentCreate(title="Example latency alert", description="Checkout p95 latency exceeded the demo threshold", service_id=payment.id, severity="medium", source="manual"))
        if not db.query(Deployment).filter_by(github_run_id="demo-1001").first():
            db.add(Deployment(repository="example/backend-api", branch="main", commit_sha="abc123demo", commit_message="Demo release", environment="production", status="successful", workflow_name="Deploy Production", github_run_id="demo-1001"))
            db.commit()
    print("Seed data created.")


if __name__ == "__main__":
    main()
