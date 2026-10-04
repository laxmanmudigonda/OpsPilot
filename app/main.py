import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from redis import Redis

from app.api.routes import health, incidents, services, webhooks
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_context

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
REQUESTS = Counter("opspilot_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("opspilot_http_request_duration_seconds", "HTTP latency", ["path"])
ACTIVE_INCIDENTS = Gauge("opspilot_active_incidents", "Active incident count")

app = FastAPI(
    title="OpsPilot",
    version="1.0.0",
    description="Event-driven DevOps incident management for Slack, GitHub, and monitored services.",
)
app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(services.router)
app.include_router(webhooks.router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    try:
        if request.url.path.startswith("/webhooks/") and await rate_limited(request):
            response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        else:
            response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled request failure", extra={"error_type": type(exc).__name__})
        raise
    finally:
        LATENCY.labels(path=route_label(request.url.path)).observe(time.perf_counter() - started)
        request_id_context.reset(token)
    response.headers["X-Request-ID"] = request_id
    REQUESTS.labels(method=request.method, path=route_label(request.url.path), status=response.status_code).inc()
    return response


async def rate_limited(request: Request) -> bool:
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate:{client_ip}:{int(time.time() // 60)}"
    client = Redis.from_url(settings.redis_url, socket_timeout=0.1)
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, 70)
        return count > 120
    except Exception:
        return False
    finally:
        client.close()


def route_label(path: str) -> str:
    if path.startswith("/api/incidents/"):
        return "/api/incidents/{id}"
    if path.startswith("/api/services/"):
        return "/api/services/{id}"
    return path


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
