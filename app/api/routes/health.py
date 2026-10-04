from fastapi import APIRouter, Response, status
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "opspilot"}


@router.get("/health/db")
def health_db(response: Response) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "healthy", "component": "database"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "component": "database"}


@router.get("/health/redis")
def health_redis(response: Response) -> dict[str, str]:
    client = Redis.from_url(get_settings().redis_url, socket_timeout=1)
    try:
        client.ping()
        return {"status": "healthy", "component": "redis"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "component": "redis"}
    finally:
        client.close()
