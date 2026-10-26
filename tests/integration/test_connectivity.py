"""Integration tests for connectivity and health API endpoints.
Verifies ENV-01 and ENV-02 requirements:
- Clean healthcheck schema and response
- Degraded / 503 handling when databases are offline without hanging
- Environment metadata disclosure with strict secret redaction
- Resource quota verification (DEC-002: 2.0 vCPU, 2048m RAM)
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.adapters.base import HealthStatus
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns API summary and links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "benchlab"
    assert "health" in data
    assert "environment" in data


def test_health_endpoint_schema():
    """Verify health endpoint structure conforms to HealthResponse model."""
    response = client.get("/api/health")
    # Response can be 200 (if DBs online) or 503 (if DBs offline), but MUST return valid json
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert "timestamp" in data
    assert "engines" in data
    assert "postgresql" in data["engines"]
    assert "mongodb" in data["engines"]


def test_health_endpoint_when_all_healthy():
    """Verify 200 status code when both database engines are healthy."""
    mock_pg = HealthStatus(
        is_healthy=True,
        engine="postgresql",
        version="PostgreSQL 17.2-alpine",
        latency_ms=1.2,
        connection_info={"host": "127.0.0.1", "port": 5432},
    )
    mock_mongo = HealthStatus(
        is_healthy=True,
        engine="mongodb",
        version="MongoDB 8.0.4",
        latency_ms=0.8,
        connection_info={"host": "127.0.0.1", "port": 27017},
    )

    with patch("app.api.health.PostgresAdapter.health", return_value=mock_pg), \
         patch("app.api.health.MongoAdapter.health", return_value=mock_mongo):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["engines"]["postgresql"]["is_healthy"] is True
        assert data["engines"]["mongodb"]["is_healthy"] is True


def test_health_endpoint_when_one_engine_degraded_env_02():
    """Verify ENV-02 requirement: Stopping/losing one database returns 503 degraded, no infinite hang."""
    mock_pg = HealthStatus(
        is_healthy=True,
        engine="postgresql",
        version="PostgreSQL 17.2-alpine",
        latency_ms=1.2,
        connection_info={"host": "127.0.0.1", "port": 5432},
    )
    mock_mongo_down = HealthStatus(
        is_healthy=False,
        engine="mongodb",
        version=None,
        latency_ms=10.5,
        connection_info={"host": "127.0.0.1", "port": 27017},
        error="MongoDB connection error: connection refused",
    )

    with patch("app.api.health.PostgresAdapter.health", return_value=mock_pg), \
         patch("app.api.health.MongoAdapter.health", return_value=mock_mongo_down):
        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["engines"]["postgresql"]["is_healthy"] is True
        assert data["engines"]["mongodb"]["is_healthy"] is False
        assert "connection refused" in data["engines"]["mongodb"]["error"]


def test_health_endpoint_when_both_engines_unhealthy():
    """Verify 503 unhealthy when both database engines are down."""
    mock_pg_down = HealthStatus(
        is_healthy=False,
        engine="postgresql",
        error="Postgres down",
        connection_info={},
    )
    mock_mongo_down = HealthStatus(
        is_healthy=False,
        engine="mongodb",
        error="Mongo down",
        connection_info={},
    )

    with patch("app.api.health.PostgresAdapter.health", return_value=mock_pg_down), \
         patch("app.api.health.MongoAdapter.health", return_value=mock_mongo_down):
        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"


def test_environment_endpoint_and_quota_env_01():
    """Verify ENV-01 requirement: Host environment, versions, and 2 vCPU / 2048m quota."""
    response = client.get("/api/environment")
    assert response.status_code == 200
    data = response.json()

    assert data["project_name"] == "benchlab"
    assert data["spec_version"] == "1.0"
    assert "host" in data
    assert "processor" in data["host"]
    assert "total_memory_gib" in data["host"]
    assert "python_version" in data

    # Target database versions & resource quotas (DEC-001, DEC-002)
    db_targets = data["database_targets"]
    assert db_targets["postgresql_target_version"] == "17.2-alpine"
    assert db_targets["mongodb_target_version"] == "8.0.4"
    assert db_targets["cpu_limit_quota"] == 2.0
    assert db_targets["memory_limit_quota"] == "2048m"


def test_environment_strictly_redacts_secrets():
    """Verify that passwords, tokens, and secrets are NEVER returned in API responses."""
    response = client.get("/api/environment")
    assert response.status_code == 200
    data = response.json()
    config = data["config"]

    # Verify sensitive keys are redacted
    assert config["postgres_password"] == "***REDACTED***"
    assert config["mongo_initdb_root_password"] == "***REDACTED***"

    # Verify DSNs do not contain raw passwords
    assert "benchlab_dev_password_change_me" not in config["postgres_dsn"]
    assert "benchlab_dev_password_change_me" not in config["mongo_uri"]
    assert "***REDACTED***" in config["postgres_dsn"]
    assert "***REDACTED***" in config["mongo_uri"]


def test_live_databases_connectivity():
    """Verify live connectivity, versions, and latency against running Docker containers."""
    from app.adapters import PostgresAdapter, MongoAdapter

    # Test PostgreSQL live
    pg_adapter = PostgresAdapter()
    pg_health = pg_adapter.health(timeout_seconds=5.0)
    assert pg_health.is_healthy is True, f"PostgreSQL is unhealthy: {pg_health.error}"
    assert "17." in pg_health.version
    assert pg_health.latency_ms > 0
    assert "password" not in pg_health.connection_info

    # Test executing a simple query
    pg_res = pg_adapter.execute("live_test_pg", {"sql": "SELECT 1 AS num;"})
    assert pg_res.data == [{"num": 1}]
    pg_adapter.close()

    # Test MongoDB live
    mongo_adapter = MongoAdapter()
    mongo_health = mongo_adapter.health(timeout_seconds=5.0)
    assert mongo_health.is_healthy is True, f"MongoDB is unhealthy: {mongo_health.error}"
    assert "8.0." in mongo_health.version
    assert mongo_health.latency_ms > 0
    assert "password" not in mongo_health.connection_info

    # Test executing a find command on mongo
    mongo_res = mongo_adapter.execute("live_test_mongo", {"collection": "test_collection", "type": "find", "filter": {}})
    assert mongo_res.status == "success"
    mongo_adapter.close()

    # Test live /api/health returns 200 and healthy
    live_response = client.get("/api/health")
    assert live_response.status_code == 200
    live_data = live_response.json()
    assert live_data["status"] == "healthy"
    assert live_data["engines"]["postgresql"]["is_healthy"] is True
    assert live_data["engines"]["mongodb"]["is_healthy"] is True

