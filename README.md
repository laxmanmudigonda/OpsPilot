<div align="center">

# OpsPilot

### Slack-native incident management for engineering teams

Detect service failures, coordinate response from Slack, correlate failed GitHub Actions runs, and preserve a complete incident timeline—without requiring a paid platform.

[![CI](https://github.com/laxmanmudigonda/OpsPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/laxmanmudigonda/OpsPilot/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Quick start](#quick-start) · [Architecture](#architecture) · [Slack integration](#slack-integration) · [API](#api-surface) · [Documentation](#documentation)

</div>

---

## What is OpsPilot?

OpsPilot is a local-first, event-driven incident-management platform built around the way engineering teams already work. It monitors registered HTTP services, creates deduplicated incidents when health changes, and lets responders acknowledge, assign, investigate, and resolve incidents directly from Slack.

GitHub Actions workflow events are ingested through signed webhooks and processed asynchronously. Every important mutation is preserved as an immutable incident event, making the complete response timeline available for audits and post-incident review.

This project focuses on backend and reliability engineering rather than a large frontend. It demonstrates API design, asynchronous workers, transactions, distributed coordination, webhook security, retries, idempotency, observability, containerization, and failure handling in one reproducible system.

## Highlights

- **Slack-native operations** — `/incident`, `/incidents`, `/service-status`, and interactive Block Kit actions
- **Automated service monitoring** — scheduled HTTP checks, latency-bounded requests, state transitions, and recovery detection
- **Auditable incident lifecycle** — centralized state machine plus immutable timeline events
- **GitHub Actions correlation** — signed `workflow_run` ingestion, deployment records, and optional incidents on failures
- **Asynchronous processing** — Celery workers and scheduler backed by Redis
- **Reliability controls** — row locks, idempotent actions, webhook delivery deduplication, monitor locks, and bounded retries
- **Security by default** — API-key protection, Slack replay prevention, GitHub HMAC verification, non-root containers, and environment-only secrets
- **Operational visibility** — structured JSON logs, request IDs, dependency health checks, and Prometheus metrics
- **Free local demo** — PostgreSQL, Redis, API, workers, scheduler, and a controllable failure simulator in Docker Compose
- **Post-incident reporting** — deterministic summaries that work without a paid AI provider

## Architecture

```mermaid
flowchart LR
    Slack[Slack commands and actions] -->|Signed requests| API[FastAPI]
    GitHub[GitHub Actions] -->|Signed webhooks| API
    Client[REST clients] -->|API key| API

    API --> DB[(PostgreSQL)]
    API --> Queue[(Redis)]
    Beat[Celery beat] --> Queue
    Queue --> Workers[Celery workers]

    Workers --> Targets[Monitored services]
    Workers --> DB
    Workers --> Slack

    API --> Metrics[Prometheus metrics]
```

The API authenticates and validates incoming work. PostgreSQL is the authoritative state store. Redis brokers background jobs, rate limits webhooks, and coordinates per-service monitor locks. Celery workers perform network-dependent work with bounded retries, while Celery beat schedules health checks.

### Incident lifecycle

```mermaid
stateDiagram-v2
    [*] --> Open
    Open --> Acknowledged
    Open --> Investigating
    Open --> Resolved
    Acknowledged --> Investigating
    Acknowledged --> Monitoring
    Acknowledged --> Resolved
    Investigating --> Monitoring
    Investigating --> Resolved
    Monitoring --> Investigating
    Monitoring --> Resolved
    Resolved --> [*]
```

Invalid transitions—such as `resolved → acknowledged`—are rejected. Incident state and its timeline event are committed together.

## Example workflow

1. Celery checks `Demo Payment API` and receives HTTP 500.
2. OpsPilot detects `healthy → down` and creates a single monitoring incident.
3. A structured incident card appears in `#incidents`.
4. A responder clicks **Acknowledge**, **Assign to Me**, and **Investigating**.
5. The service recovers; OpsPilot records a recovery event but leaves closure to a human.
6. The responder clicks **Resolve**.
7. OpsPilot stores the duration, complete timeline, actors, and deterministic incident summary.

## Tech stack

- **API:** Python 3.12, FastAPI, Pydantic, Uvicorn
- **Persistence:** PostgreSQL 16, SQLAlchemy 2, Alembic
- **Async processing:** Redis 7, Celery, Celery beat
- **Integrations:** Slack Web API and Block Kit, GitHub Webhooks, HTTPX
- **Observability:** structured JSON logging, request IDs, Prometheus client
- **Quality:** pytest, pytest-cov, Ruff, GitHub Actions
- **Runtime:** Docker and Docker Compose

## Quick start

### Prerequisites

- Docker Desktop with the Linux engine running
- PowerShell
- Git, if you plan to contribute

### Start the stack

```powershell
git clone https://github.com/laxmanmudigonda/OpsPilot.git
Set-Location OpsPilot
Copy-Item .env.example .env
```

Generate an API key and place it in `.env`:

```powershell
[Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
```

Start every component:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:18000/health
```

Local endpoints:

- API and OpenAPI: <http://localhost:18000/docs>
- API health: <http://localhost:18000/health>
- Demo service: <http://localhost:18080/health>
- Prometheus metrics: <http://localhost:18000/metrics>

The one-shot `migrate` container should exit with code `0`; that means Alembic completed successfully.

## Configuration

Core local configuration:

```env
ENVIRONMENT=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://opspilot:opspilot@postgres:5432/opspilot
REDIS_URL=redis://redis:6379/0
API_KEY=replace-with-a-long-random-value
MONITOR_INTERVAL=15
MONITOR_TIMEOUT=5
AUTO_INCIDENT_ON_DEPLOY_FAILURE=true
AI_PROVIDER=disabled
```

Optional integration configuration:

```env
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
SLACK_INCIDENT_CHANNEL_ID=
GITHUB_WEBHOOK_SECRET=
GITHUB_TOKEN=
AI_API_KEY=
```

The application is fully usable through REST without Slack, GitHub, or AI credentials. `.env` is ignored by Git; only placeholder values belong in `.env.example`.

## Run the complete demo

The demo service exposes `POST /fail` and `POST /recover`. The automated scenario registers the service, triggers failure, waits for monitoring, acknowledges and assigns the incident, restores health, resolves the incident, and prints the timeline and summary.

```powershell
docker compose exec `
  -e OPSPILOT_URL=http://api:8000 `
  -e DEMO_SERVICE_URL=http://demo-service:8080 `
  api python scripts/demo.py
```

Seed additional screenshot-friendly data:

```powershell
docker compose exec api python scripts/seed.py
```

## Slack integration

1. Create a Slack app and add the bot scopes `chat:write` and `commands`.
2. Install it to the workspace and copy its bot token, signing secret, and incident channel ID into `.env`.
3. Invite the app to the incident channel.
4. Expose local port `18000` through a temporary HTTPS tunnel for development.
5. Set Interactivity and all slash-command request URLs to `https://YOUR_HOST/webhooks/slack`.
6. Create `/incident`, `/incidents`, and `/service-status` commands.
7. Restart the API and worker after changing environment variables.

Examples:

```text
/incident create demo-payment-api Checkout requests are failing
/incidents
/service-status
```

Slack requests are verified using HMAC-SHA256 over the exact raw body. Requests older than five minutes are rejected to reduce replay risk. Button actions use the same signed endpoint and update the authoritative incident state transactionally.

## GitHub integration

1. Generate a high-entropy `GITHUB_WEBHOOK_SECRET` and restart the API.
2. In repository **Settings → Webhooks**, create a webhook targeting `https://YOUR_HOST/webhooks/github`.
3. Choose `application/json`, enter the same secret, and subscribe only to **Workflow runs**.
4. Keep SSL verification and the webhook active.

OpsPilot stores the provider delivery ID before queueing processing. Duplicate deliveries return safely without repeating the deployment or incident side effect. Failed workflow runs create high-severity incidents when `AUTO_INCIDENT_ON_DEPLOY_FAILURE=true`.

`GITHUB_TOKEN` is optional in the current version because webhook ingestion does not require outbound GitHub REST calls.

## API surface

All `/api/*` routes require the `X-API-Key` header.

```text
POST   /api/incidents
GET    /api/incidents
GET    /api/incidents/{id}
POST   /api/incidents/{id}/acknowledge
POST   /api/incidents/{id}/assign
PATCH  /api/incidents/{id}/status
POST   /api/incidents/{id}/resolve
GET    /api/incidents/{id}/timeline
POST   /api/incidents/{id}/summary
GET    /api/incidents/{id}/summary

POST   /api/services
GET    /api/services
GET    /api/services/{id}

POST   /webhooks/slack
POST   /webhooks/github

GET    /health
GET    /health/db
GET    /health/redis
GET    /metrics
```

Incident listing supports status, severity, service, pagination, and ordering filters. The live OpenAPI specification is available at `/docs`.

## Reliability by design

- **Idempotency:** unique webhook delivery IDs and processing status prevent duplicate consumption.
- **Incident deduplication:** monitoring checks for an unresolved incident before creating another.
- **Concurrency:** `SELECT ... FOR UPDATE` protects simultaneous incident mutations.
- **Atomic auditability:** important state changes and their `IncidentEvent` records share a transaction.
- **Distributed coordination:** Redis `SET NX EX` locks prevent overlapping checks of the same service.
- **Retry discipline:** transient worker failures use capped exponential backoff with jitter.
- **Eventual consistency:** webhook ingestion acknowledges durable receipt before workers apply downstream effects.
- **Failure visibility:** database and Redis health endpoints report dependency failures explicitly.

## Security

- Slack and GitHub signatures use constant-time HMAC comparison.
- Slack timestamps provide replay protection.
- Internal REST endpoints require an API key.
- Pydantic validates sizes, enum values, URLs, and status codes.
- SQLAlchemy parameterizes database queries.
- Tokens, request bodies, and signatures are excluded from logs.
- Application containers run as a non-root user.
- Secrets are environment-only and `.env` is never committed.

See the full [security architecture](docs/security.md), including the health-check SSRF boundary and recommended production controls.

## Testing and quality

```powershell
docker compose run --rm api pytest --cov=app --cov-report=term-missing
docker compose run --rm api ruff check .
docker compose build
```

The verified local suite covers incident creation and lifecycle operations, timelines, summaries, service registration, health transitions, monitor timeouts, duplicate incident prevention, Slack and GitHub signatures, duplicate webhook delivery, failed-deployment deduplication, API authentication, and health checks. External APIs are mocked; CI requires no real Slack or GitHub credentials.

Run the dependency-free local benchmark only when the API is active:

```powershell
docker compose exec api python scripts/benchmark.py --url http://api:8000/health
```

No benchmark numbers are claimed without an actual recorded run.

## Repository structure

```text
app/
├── api/routes/       REST, health, Slack, and GitHub endpoints
├── core/             configuration, logging, and security
├── db/               SQLAlchemy models and sessions
├── repositories/     query-oriented data access
├── schemas/          request and response models
├── services/         incident, monitoring, integration, and summary logic
└── workers/          Celery application, scheduled work, and retryable tasks

alembic/              database migrations
scripts/              simulator, seed, demo, and benchmark tools
tests/                lifecycle, monitoring, security, and webhook tests
docs/                 architecture, scaling, security, interview, and resume notes
.github/workflows/    continuous integration
```

## Documentation

- [Architecture](docs/architecture.md) — components, trust boundaries, and data flow
- [System design](docs/system-design.md) — scaling, failure behavior, delivery guarantees, and CAP trade-offs
- [Security](docs/security.md) — secrets, webhook verification, SSRF, and production hardening
- [Interview guide](docs/interview-guide.md) — concise answers to common backend and SRE questions
- [Resume material](docs/resume.md) — accurate project descriptions and bullet points

## Known limitations

OpsPilot is production-style portfolio software, not an audited production service. The current version intentionally omits multi-region HA, a transactional outbox, dead-letter administration, Slack OAuth multi-tenancy, network-level SSRF enforcement, protected metrics, and full message synchronization for incidents changed outside Slack. Temporary tunnel URLs are suitable for local demonstrations only.

## Roadmap

- Transactional outbox and dead-letter replay tooling
- Slack rate-limit-aware message synchronization
- Per-tenant RBAC and Slack OAuth installation flow
- Service-to-repository and deployment-to-incident correlation rules
- OpenTelemetry traces and richer Prometheus metrics
- Disposable PostgreSQL/Redis integration tests
- Distributed due-check partitioning for large service fleets

## License

Released under the [MIT License](LICENSE).

---

<div align="center">
Built by <a href="https://github.com/laxmanmudigonda">Laxman Prasad Mudigonda</a> as a backend, DevOps, and reliability engineering portfolio project.
</div>
