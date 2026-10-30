"""Health check endpoint for BenchLab.
Verifies API server status and connectivity to PostgreSQL and MongoDB.
Returns 503 if any required database is down (as required by SPEC 9.2).
"""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.adapters import get_adapter
from app.adapters.postgres import PostgresAdapter
from app.adapters.mongodb import MongoAdapter
from app.config import get_settings

router = APIRouter(tags=["Health"])


class EngineHealthResponse(BaseModel):
    is_healthy: bool
    engine: str
    version: str | None = None
    latency_ms: float | None = None
    connection_info: Dict[str, Any]
    error: str | None = None


class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    timestamp: str
    api: str
    engines: Dict[str, EngineHealthResponse]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check for API and Database engines",
)
def get_health(response: Response) -> HealthResponse:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    # Inspect PostgreSQL health with bounded timeout
    pg_adapter = get_adapter("postgresql")
    pg_status = pg_adapter.health(timeout_seconds=2.0)

    # Inspect MongoDB health with bounded timeout
    mongo_adapter = get_adapter("mongodb")
    mongo_status = mongo_adapter.health(timeout_seconds=2.0)

    # Determine overall cluster health
    if pg_status.is_healthy and mongo_status.is_healthy:
        overall_status = "healthy"
        response.status_code = status.HTTP_200_OK
    elif pg_status.is_healthy or mongo_status.is_healthy:
        overall_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        timestamp=now_utc,
        api="ok",
        engines={
            "postgresql": EngineHealthResponse(**pg_status.to_dict()),
            "mongodb": EngineHealthResponse(**mongo_status.to_dict()),
        },
    )
