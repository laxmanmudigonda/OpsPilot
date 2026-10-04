# Security

Secrets are environment-only and `.env` is ignored. Internal REST routes require `X-API-Key`; health and metrics are intentionally unauthenticated for orchestration and should be network-restricted in production. Slack and GitHub signatures are compared in constant time. Slack timestamps prevent replay, and GitHub delivery IDs prevent duplicate processing.

SQLAlchemy parameterizes queries. Pydantic constrains sizes, enum values, slugs, status codes, and URLs. Logs do not record tokens, request bodies, or signatures. The container runs as a non-root user.

Health-check URLs create an SSRF risk. The local demo intentionally permits Docker-internal HTTP. In a public deployment, validate resolved IPs against an allowlist, reject loopback/private/link-local destinations unless explicitly approved, re-check after DNS resolution, disable redirects (already done), and apply network egress policy.

Before public use: rotate the API key, terminate TLS at a trusted proxy, restrict `/metrics`, use a secrets manager, configure CORS only if needed, apply database least privilege, encrypt backups, scan images and dependencies, and add audit retention policy. This portfolio build is production-style, not a claim of audited production readiness.
