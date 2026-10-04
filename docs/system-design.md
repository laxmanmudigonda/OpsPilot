# System design and scaling

## Consistency and delivery

PostgreSQL is the source of truth. API replicas are stateless and can scale behind a load balancer. Workers are horizontally scalable because tasks carry identifiers, not database sessions. Processing is at-least-once: Celery may redeliver after a worker crash, so the `WebhookEvent` status and unique delivery constraint make handlers idempotent. Incident state changes are strongly consistent within a database transaction; Slack notifications and monitoring results are eventually consistent.

The current enqueue-after-commit flow has a small crash window. A production evolution would use a transactional outbox table, publish unsent rows, and retain a dead-letter queue. Event ordering can be enforced per incident using versions or partitioned queues if volume warrants it.

## Scaling monitoring

For 10,000 services, beat should page eligible services by `last_checked_at`, partition tasks across queues, add jitter, and enforce per-host concurrency and egress policies. Redis locks prevent two workers checking the same service concurrently. PostgreSQL indexes cover active incident and status queries. Read replicas can serve history; primary writes remain transactional. Redis Sentinel/Cluster and managed PostgreSQL with backups are sensible production upgrades.

## Limits and failures

- Redis failure prevents new asynchronous work, but the REST API and stored incident history remain available. Health checks expose the fault. An outbox would allow later replay.
- PostgreSQL failure makes mutations unavailable; the API returns errors and does not claim success. Use multi-AZ failover, backups, and connection-pool limits in production.
- Slack rate limits should honor `Retry-After`; Celery retries transient errors with jitter and caps attempts. Authentication/permission errors are permanent and should not retry.
- A Redis fixed-window limit protects webhooks at 120 requests/minute/IP. Production ingress should add proxy/WAF limits and trusted proxy configuration.
- CAP tradeoff: during a database partition, OpsPilot favors consistency for incident state over accepting writes that could conflict.
