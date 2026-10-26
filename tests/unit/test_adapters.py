"""Unit tests for Database Adapters (PostgreSQL and MongoDB).
Tests error handling, connection failures, timeouts, credential errors, and factory.
"""

import time
import pytest
from app.adapters import (
    BaseAdapter,
    HealthStatus,
    IndexInfo,
    MongoAdapter,
    PostgresAdapter,
    QueryResult,
    get_adapter,
)
from app.config import Settings


def test_adapter_factory():
    """Verify get_adapter factory returns correct adapter instances."""
    pg = get_adapter("postgresql")
    assert isinstance(pg, PostgresAdapter)

    pg2 = get_adapter("postgres")
    assert isinstance(pg2, PostgresAdapter)

    mg = get_adapter("mongodb")
    assert isinstance(mg, MongoAdapter)

    mg2 = get_adapter("mongo")
    assert isinstance(mg2, MongoAdapter)

    with pytest.raises(ValueError) as excinfo:
        get_adapter("invalid_engine")
    assert "Unsupported engine" in str(excinfo.value)


def test_postgres_adapter_unreachable_host():
    """Verify PostgresAdapter handles down / unreachable host without hanging or crashing."""
    dummy_settings = Settings(
        postgres_host="127.0.0.1",
        postgres_port=59999,  # Non-existent port
        client_timeout_seconds=2,
    )
    adapter = PostgresAdapter(settings=dummy_settings)

    t0 = time.perf_counter()
    health = adapter.health(timeout_seconds=1.0)
    elapsed = time.perf_counter() - t0

    assert health.is_healthy is False
    assert health.engine == "postgresql"
    assert health.version is None
    assert health.error is not None
    assert "PostgreSQL connection error" in health.error
    # Must not hang indefinitely (bounded by timeout)
    assert elapsed < 5.0

    # Ensure connection info is sanitized (no password)
    assert "password" not in health.connection_info
    assert health.connection_info["port"] == 59999

    adapter.close()


def test_postgres_adapter_invalid_credentials():
    """Verify PostgresAdapter handles wrong credentials gracefully."""
    bad_creds = Settings(
        postgres_user="non_existent_user_xyz",
        postgres_password="wrong_password_xyz",
        client_timeout_seconds=2,
    )
    adapter = PostgresAdapter(settings=bad_creds)
    health = adapter.health(timeout_seconds=1.0)

    assert health.is_healthy is False
    assert health.error is not None
    assert "password" not in health.connection_info
    adapter.close()


def test_mongo_adapter_unreachable_host():
    """Verify MongoAdapter handles unreachable server without hanging or crashing."""
    dummy_settings = Settings(
        mongo_host="127.0.0.1",
        mongo_port=59998,  # Non-existent port
        client_timeout_seconds=2,
    )
    adapter = MongoAdapter(settings=dummy_settings)

    t0 = time.perf_counter()
    health = adapter.health(timeout_seconds=1.0)
    elapsed = time.perf_counter() - t0

    assert health.is_healthy is False
    assert health.engine == "mongodb"
    assert health.version is None
    assert health.error is not None
    assert "MongoDB connection error" in health.error
    # Must terminate within reasonable window
    assert elapsed < 5.0

    # Ensure connection info is sanitized
    assert "password" not in health.connection_info
    assert health.connection_info["port"] == 59998

    adapter.close()


def test_mongo_adapter_invalid_credentials():
    """Verify MongoAdapter handles invalid credentials without leaking password."""
    bad_creds = Settings(
        mongo_initdb_root_username="invalid_mongo_user",
        mongo_initdb_root_password="invalid_password",
        client_timeout_seconds=2,
    )
    adapter = MongoAdapter(settings=bad_creds)
    health = adapter.health(timeout_seconds=1.0)

    # When host is down or creds invalid, is_healthy is False
    assert health.is_healthy is False
    assert "password" not in health.connection_info
    adapter.close()


def test_health_status_to_dict():
    """Verify HealthStatus serialization formatting."""
    hs = HealthStatus(
        is_healthy=True,
        engine="postgresql",
        version="PostgreSQL 17.2",
        latency_ms=1.23456,
        connection_info={"host": "127.0.0.1", "port": 5432},
    )
    d = hs.to_dict()
    assert d["is_healthy"] is True
    assert d["engine"] == "postgresql"
    assert d["latency_ms"] == 1.235
    assert d["version"] == "PostgreSQL 17.2"
