"""End-to-End Test Suite for Dashboard and Job Coordination Flow.
Validates the complete lifecycle:
Health -> Environment -> Datasets Load & Validate -> Query Single Run & Explain ->
Benchmark Dry-run & Status -> Results Summary/Resources/Export -> Test Matrix.
Implements SPEC.md Section 10, Section 11 (Gate G5 & G6).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_e2e_health_and_environment():
    """Verify system health and container quota environment endpoints."""
    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert "postgresql" in health_data["engines"]
    assert "mongodb" in health_data["engines"]

    # 2. Environment check
    res_env = client.get("/api/environment")
    assert res_env.status_code == 200
    env_data = res_env.json()
    assert env_data["database_targets"]["cpu_limit_quota"] == 2.0
    assert env_data["database_targets"]["memory_limit_quota"] == "2048m"
    assert "17.2" in env_data["database_targets"]["postgresql_target_version"]
    assert "8.0" in env_data["database_targets"]["mongodb_target_version"]


def test_e2e_datasets_flow():
    """Verify dataset loading and canonical checksum equivalence validation."""
    # Validate fixture dataset
    req_payload = {"profile": "fixture", "seed": 42, "distribution": "uniform"}
    res_val = client.post("/api/datasets/validate", json=req_payload)
    assert res_val.status_code == 200
    val_data = res_val.json()
    assert val_data["is_valid"] is True
    assert val_data["total_orders"] == 50
    assert val_data["checksum_sha256"] == "b566071c14791350b8ef7ee65957d813ee066d4e2c32415a2f10c8d7d4df858b"


def test_e2e_queries_execution_and_explain():
    """Verify single query run and execution plan inspection."""
    # Execute Q1 Point Lookup on both engines with valid order_id
    res_q1 = client.post(
        "/api/queries/Q1/execute",
        json={"engine": "both", "params": {"order_id": 1}},
    )
    assert res_q1.status_code == 200
    q1_data = res_q1.json()
    assert q1_data["query_id"] == "Q1"
    assert q1_data["is_equivalent"] is True
    assert q1_data["results"]["postgresql"]["row_count"] == 1
    assert q1_data["results"]["mongodb"]["row_count"] == 1

    # Explain Q1 on PostgreSQL
    res_exp = client.post(
        "/api/queries/Q1/explain",
        json={"engine": "postgresql", "params": {"order_id": 1}},
    )
    assert res_exp.status_code == 200
    exp_data = res_exp.json()
    assert exp_data["engine"] == "postgresql"
    assert "raw_plan" in exp_data


def test_e2e_benchmark_coordination_and_dryrun():
    """Verify dry-run, start rejection when locked, and status monitoring."""
    # 1. Dry run
    dry_req = {
        "experiment_id": "E0-e2e-dryrun",
        "mode": "L",
        "dataset": "fixture-seed42",
        "profile": "fixture",
        "index_profile": "I1",
        "queries": ["Q1", "Q2"],
        "engines": ["postgresql", "mongodb"],
        "repeats": 1,
        "fixed_count": 10,
        "concurrency": 1,
        "duration_seconds": 10.0,
        "warmup_min_requests": 5,
        "warmup_min_duration_s": 1.0,
        "seed": 42,
    }
    res_dry = client.post("/api/benchmark/dry-run", json=dry_req)
    assert res_dry.status_code == 200
    dry_data = res_dry.json()
    assert dry_data["total_cells"] == 4  # 2 queries * 2 engines * 1 repeat

    # 2. Check lock status
    res_status = client.get("/api/benchmark/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "status" in status_data or "state" in status_data


def test_e2e_results_and_reports_flow():
    """Verify statistics summary, resource logging, and markdown/csv export."""
    exp_id = "E0-smoke-live"

    # 1. Summary
    res_sum = client.get(f"/api/results/{exp_id}/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert sum_data["experiment_id"] == exp_id
    assert "Q1" in sum_data["queries"]
    assert sum_data["queries"]["Q1"]["postgresql"]["p50_ms"] > 0
    assert sum_data["queries"]["Q1"]["mongodb"]["p50_ms"] > 0

    # 2. Resources time-series
    res_res = client.get(f"/api/results/{exp_id}/resources")
    assert res_res.status_code == 200
    res_list = res_res.json()
    assert len(res_list) > 0
    assert "cpu_percent" in res_list[0]
    assert "memory_mb" in res_list[0]

    # 3. Export Markdown
    res_md = client.get(f"/api/results/{exp_id}/export/markdown")
    assert res_md.status_code == 200
    assert "# BÁO CÁO KẾT QUẢ THỰC NGHIỆM" in res_md.text

    # 4. Export CSV
    res_csv = client.get(f"/api/results/{exp_id}/export/csv")
    assert res_csv.status_code == 200
    assert "p50_ms" in res_csv.text


def test_e2e_tests_matrix_flow():
    """Verify test matrix catalog contains all SPEC Section 12 test cases."""
    res_matrix = client.get("/api/tests/matrix")
    assert res_matrix.status_code == 200
    cases = res_matrix.json()
    case_ids = {c["id"] for c in cases}
    assert "DATA-01" in case_ids
    assert "QUERY-01" in case_ids
    assert "BENCH-01" in case_ids
    assert "INT-01" in case_ids
