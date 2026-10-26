"""Integration tests for Dataset API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_dataset_profiles():
    """Verify GET /api/datasets/profiles returns all 4 standard profiles."""
    response = client.get("/api/datasets/profiles")
    assert response.status_code == 200
    data = response.json()

    assert "fixture" in data
    assert "small" in data
    assert "medium" in data
    assert "large" in data

    assert data["fixture"]["num_orders"] == 50
    assert data["small"]["num_orders"] == 10000
    assert data["medium"]["num_orders"] == 100000
    assert data["large"]["num_orders"] == 1000000


def test_validate_profile_dataset_api():
    """Verify POST /api/datasets/validate runs canonical validation and returns SHA-256."""
    payload = {
        "profile": "fixture",
        "seed": 42,
        "distribution": "uniform",
    }
    response = client.post("/api/datasets/validate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_valid"] is True
    assert data["total_customers"] == 12
    assert data["total_products"] == 20
    assert data["total_orders"] == 50
    assert data["total_items"] == 174
    assert data["error_count"] == 0
    # Must match deterministic hash
    assert data["checksum_sha256"] == "b566071c14791350b8ef7ee65957d813ee066d4e2c32415a2f10c8d7d4df858b"


def test_validate_invalid_profile():
    """Verify 400 error when requested profile does not exist."""
    response = client.post("/api/datasets/validate", json={"profile": "non_existent_profile"})
    assert response.status_code == 400
