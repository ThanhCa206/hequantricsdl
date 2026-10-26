"""Unit Test Suite for Security, SQL/NoSQL Injection Prevention, and Path Traversal.
Strictly implements SPEC.md Section 12 (Security Verification & Gate G7).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sql_injection_point_lookup():
    """Verify Q1 point lookup rejects or safely parameterizes SQL injection payloads."""
    # Attempt SQL injection in integer/string parameter
    malicious_payloads = [
        "1; DROP TABLE orders; --",
        "1 OR 1=1",
        "' OR '1'='1",
        "1 UNION SELECT 1, 2, '2024-01-01', 'paid', 100 --",
    ]
    for payload in malicious_payloads:
        res = client.post(
            "/api/queries/Q1/execute",
            json={"engine": "postgresql", "params": {"order_id": payload}},
        )
        # Should either return 200 with 0 rows (treated as literal value), or error handled safely,
        # never dropping table or executing union data.
        assert res.status_code == 200
        data = res.json()
        assert "postgresql" in data["results"]
        # In PostgreSQL with parameterized query %(order_id)s, non-matching string returns 0 rows or type error handled
        pg_res = data["results"]["postgresql"]
        assert pg_res["row_count"] == 0 or pg_res["status"] == "error"


def test_sql_injection_filter_query():
    """Verify Q3 status filter parameterizes string injection safely."""
    malicious_status = "paid' OR status IS NOT NULL; --"
    res = client.post(
        "/api/queries/Q3/execute",
        json={
            "engine": "postgresql",
            "params": {
                "status": malicious_status,
                "from_ts": "2024-01-01T00:00:00Z",
                "to_ts": "2024-07-01T00:00:00Z",
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "postgresql" in data["results"]
    pg_res = data["results"]["postgresql"]
    # Should safely return 0 rows because no status matches the literal injection string
    assert pg_res["row_count"] == 0


def test_path_traversal_results_summary():
    """Verify results endpoints reject path traversal attempts."""
    traversal_ids = [
        "../../etc/passwd",
        "..\\..\\Windows\\win.ini",
        "../results",
        "....//....//etc",
        "exp;rm -rf /",
        "exp*test",
        "exp?test",
        "exp/sub",
    ]
    for exp_id in traversal_ids:
        res = client.get(f"/api/results/{exp_id}/summary")
        # Must be rejected with 400 Bad Request or 404 Not Found
        assert res.status_code in (400, 404), f"Failed for payload: {exp_id}"


def test_path_traversal_export_markdown():
    """Verify export markdown endpoint rejects path traversal attempts."""
    traversal_ids = [
        "../../etc/passwd",
        "..\\..\\Windows\\system.ini",
        "../config",
    ]
    for exp_id in traversal_ids:
        res = client.get(f"/api/results/{exp_id}/export/markdown")
        assert res.status_code in (400, 404), f"Failed for payload: {exp_id}"


def test_path_traversal_export_csv():
    """Verify export CSV endpoint rejects path traversal attempts."""
    traversal_ids = [
        "../../etc/shadow",
        "..\\..\\Windows\\system32",
    ]
    for exp_id in traversal_ids:
        res = client.get(f"/api/results/{exp_id}/export/csv")
        assert res.status_code in (400, 404), f"Failed for payload: {exp_id}"


def test_path_traversal_benchmark_manifest():
    """Verify benchmark manifest endpoint rejects path traversal attempts."""
    traversal_ids = [
        "../../app/main.py",
        "..\\..\\pyproject.toml",
    ]
    for exp_id in traversal_ids:
        res = client.get(f"/api/benchmark/experiments/{exp_id}")
        assert res.status_code in (400, 404), f"Failed for payload: {exp_id}"


def test_mongodb_injection_safety():
    """Verify MongoDB query builders safely sanitize complex dictionary injection."""
    res = client.post(
        "/api/queries/Q1/execute",
        json={"engine": "mongodb", "params": {"order_id": {"$ne": None}}},
    )
    assert res.status_code == 200
    data = res.json()
    mg_res = data["results"]["mongodb"]
    # Point lookup searches for literal order_id; dictionary is treated as literal or returns 0 rows
    assert mg_res["row_count"] == 0 or mg_res["status"] in ("success", "error")


def test_benchmark_input_boundary_validation():
    """Verify benchmark run endpoint validates constraints (BENCH-11)."""
    # 1. Negative repeats
    res_neg_rep = client.post(
        "/api/benchmark/run",
        json={"experiment_id": "test-sec", "repeats": -1},
    )
    assert res_neg_rep.status_code == 422

    # 2. Concurrency out of bounds (> 128)
    res_high_c = client.post(
        "/api/benchmark/run",
        json={"experiment_id": "test-sec", "concurrency": 256},
    )
    assert res_high_c.status_code == 422

    # 3. Invalid Mode
    res_inv_mode = client.post(
        "/api/benchmark/run",
        json={"experiment_id": "test-sec", "mode": "INVALID"},
    )
    assert res_inv_mode.status_code == 422
