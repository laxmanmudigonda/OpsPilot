# Interview guide

**Why FastAPI?** It provides typed request validation, dependency injection, automatic OpenAPI, and strong async HTTP support while keeping business logic framework-independent.

**Why PostgreSQL?** Incident transitions and audit events need transactions, constraints, row locking, JSON metadata, and durable relational queries. PostgreSQL provides all of them.

**Why Redis and workers?** Webhook senders expect fast responses, while network calls and monitoring can be slow or transiently fail. Redis brokers durable-enough local tasks and also supplies short-lived distributed monitor locks. Celery gives retries, acknowledgements, scheduling, and worker scaling.

**Why not process webhooks synchronously?** It couples provider latency to database and third-party latency, increases timeout/redelivery risk, and prevents independent scaling. OpsPilot verifies and stores the delivery before enqueueing it.

**How are duplicates handled?** `WebhookEvent(provider, external_event_id)` is unique. A repeated delivery returns `duplicate`. Workers check processing status. Monitoring searches for an unresolved monitoring incident before creating another.

**How is Slack authenticated?** The server recreates `v0:{timestamp}:{raw_body}`, signs it with the signing secret using HMAC-SHA256, compares it in constant time, and rejects requests more than five minutes old.

**How is GitHub authenticated?** It computes HMAC-SHA256 over the exact raw body and compares the result to `X-Hub-Signature-256` in constant time.

**How do retries work?** Celery retries transient connection and timeout failures with exponential backoff, jitter, and a fixed maximum. Invalid authentication and malformed payloads are permanent failures and are not retried indefinitely.

**How are races avoided?** Incident mutation loads the row with `SELECT ... FOR UPDATE`, validates the transition centrally, writes the current state and timeline event in one transaction, then commits. Idempotent repeated actions return the current state without duplicating events.

**What if Redis fails?** Queue-dependent operations pause and `/health/redis` reports failure; REST history remains readable if PostgreSQL is healthy. A production outbox would preserve tasks for replay.

**What if PostgreSQL fails?** Mutations fail rather than acknowledge work that was not persisted. Production would use redundant PostgreSQL, backups, bounded pools, and readiness-based traffic removal.

**How would this support 10,000 services?** Query only due checks, page IDs, jitter schedules, shard queues, scale workers horizontally, limit concurrency per destination, cache DNS safely, and collect time-series data outside the transactional incident database.

**How would monitoring become distributed?** Any scheduler may enqueue candidates; Redis `SET NX EX` locks prevent simultaneous checks. For stronger guarantees, lease ownership and fencing tokens prevent a paused worker from writing after its lease expires.

**Can event delivery be guaranteed?** Networks cannot provide exactly-once delivery. Use at-least-once delivery plus idempotent consumers. A transactional outbox closes the database-to-broker crash window; retries and a dead-letter queue handle poison events.

**Where is eventual consistency?** GitHub is acknowledged after durable ingestion, then deployments/incidents are updated later by a worker. Slack messages also lag database commits. Database incident state itself remains transactionally consistent.

**CAP relevance?** During a partition between API and PostgreSQL, OpsPilot rejects mutations to preserve a single consistent incident history. Redis loss reduces availability of background work without splitting authoritative state.

**Why keep an event timeline?** Current state answers “what is true”; events answer “how did it happen, who changed it, and when.” That is essential for audits and post-incident learning.

**What would you improve first?** Add a transactional outbox, robust Slack response-URL updates with rate-limit handling, network-level SSRF controls, OpenTelemetry traces, dead-letter tooling, and integration tests against disposable PostgreSQL/Redis containers.
