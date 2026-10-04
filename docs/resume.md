# Resume material

One line: Built OpsPilot, an event-driven incident-management platform integrating service health monitoring, Slack interactions, and GitHub Actions webhooks.

Two bullets:

- Engineered a FastAPI/PostgreSQL incident workflow with transactional state transitions, immutable audit timelines, signed webhook verification, and idempotent delivery processing.
- Built Redis/Celery monitoring and background processing with distributed locks, bounded retries, duplicate-incident prevention, Docker Compose, and automated CI tests.

Three-bullet alternative:

- Designed REST APIs for incident lifecycle management, service registration, filtering, pagination, and deterministic post-incident reports.
- Integrated Slack Block Kit actions and GitHub workflow-run webhooks using HMAC verification and replay/duplicate protection.
- Shipped a containerized local demo with PostgreSQL, Redis, workers, scheduler, failure simulator, structured logs, Prometheus metrics, tests, and GitHub Actions CI.

Tech: Python, FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery, Slack API, GitHub Webhooks, Docker, Alembic, pytest, Ruff, Prometheus.
