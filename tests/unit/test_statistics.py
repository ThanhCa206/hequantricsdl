"""Unit Tests for Statistics, Percentiles, Paired Bootstrap CI, and Exporters.
Strictly implements STAT-01 to STAT-05, REPORT-01, REPORT-02 (Phase 6, Gate G6).
"""

import numpy as np
import pytest
from app.reports.statistics import calculate_percentiles, paired_bootstrap_ci
from app.reports.exporter import generate_markdown_report, generate_csv_summary


def test_stat_01_percentile_calculations():
    """STAT-01: Verify exact calculation of percentiles on deterministic vector."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    res = calculate_percentiles(values)

    assert res["count"] == 10
    assert res["min_ms"] == 10.0
    assert res["max_ms"] == 100.0
    assert res["mean_ms"] == 55.0
    assert res["p50_ms"] == 55.0
    assert res["p90_ms"] == 91.0
    assert res["p95_ms"] == 95.5
    assert res["p99_ms"] == 99.1


def test_stat_02_bootstrap_ci_exploratory_warning():
    """STAT-02: When paired repeats < 5, return exploratory warning note."""
    pg_medians = [15.2, 14.8, 15.0]
    mongo_medians = [18.1, 17.9, 18.0]
    ci_res = paired_bootstrap_ci(pg_medians, mongo_medians, seed=42)

    assert ci_res["n_pairs"] == 3
    assert "CI thăm dò" in ci_res["note"]
    assert ci_res["diff_median_ms"] < 0  # PG faster than Mongo


def test_stat_03_bootstrap_ci_sufficient_repeats():
    """STAT-03: When paired repeats >= 5, compute 95% bootstrap confidence bounds."""
    pg_medians = [10.0, 12.0, 11.0, 10.5, 11.5, 10.8]
    mongo_medians = [15.0, 16.0, 15.5, 14.8, 15.2, 15.1]
    ci_res = paired_bootstrap_ci(pg_medians, mongo_medians, n_bootstrap=1000, seed=42)

    assert ci_res["n_pairs"] == 6
    assert ci_res["note"] == "95% Bootstrap Confidence Interval"
    assert ci_res["ci_95_lower_ms"] <= ci_res["diff_median_ms"] <= ci_res["ci_95_upper_ms"]


def test_stat_04_empty_values_handling():
    """STAT-04: Gracefully handle empty or 0-length sample arrays."""
    res = calculate_percentiles([])
    assert res["count"] == 0
    assert res["p50_ms"] == 0.0

    ci_res = paired_bootstrap_ci([], [])
    assert ci_res["n_pairs"] == 0
    assert ci_res["diff_median_ms"] == 0.0


def test_stat_05_markdown_and_csv_exporters():
    """STAT-05 & REPORT-01: Exporters generate clean Markdown and RFC 4180 CSV."""
    dummy_summary = {
        "experiment_id": "TEST-EXP",
        "created_at_utc": "2026-09-30T14:00:00Z",
        "status": "COMPLETED",
        "config": {"mode": "L", "dataset": "fixture-seed42"},
        "queries": {
            "Q1": {
                "postgresql": {
                    "p50_ms": 1.5,
                    "p90_ms": 2.5,
                    "p95_ms": 3.0,
                    "p99_ms": 4.0,
                    "throughput_qps": 500.0,
                    "error_rate_pct": 0.0,
                    "total_requests": 100,
                    "error_count": 0,
                    "mean_ms": 1.6,
                    "std_ms": 0.3,
                    "min_ms": 1.0,
                    "max_ms": 5.0,
                },
                "mongodb": {
                    "p50_ms": 2.0,
                    "p90_ms": 3.0,
                    "p95_ms": 3.5,
                    "p99_ms": 5.0,
                    "throughput_qps": 400.0,
                    "error_rate_pct": 0.0,
                    "total_requests": 100,
                    "error_count": 0,
                    "mean_ms": 2.1,
                    "std_ms": 0.4,
                    "min_ms": 1.2,
                    "max_ms": 6.0,
                },
                "comparison": {
                    "paired_bootstrap": {
                        "diff_median_ms": -0.5,
                        "ci_95_lower_ms": -0.7,
                        "ci_95_upper_ms": -0.3,
                        "note": "95% Bootstrap Confidence Interval",
                    }
                },
            }
        },
    }

    md = generate_markdown_report(dummy_summary)
    assert "# BÁO CÁO KẾT QUẢ THỰC NGHIỆM BENCHMARK: TEST-EXP" in md
    assert "PostgreSQL" in md
    assert "MongoDB" in md

    csv_data = generate_csv_summary(dummy_summary)
    assert "experiment_id,query_id,engine,p50_ms" in csv_data
    assert "TEST-EXP,Q1,postgresql,1.5" in csv_data
    assert "TEST-EXP,Q1,mongodb,2.0" in csv_data
