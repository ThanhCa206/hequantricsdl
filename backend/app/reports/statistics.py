"""Statistics, Percentile Calculation, and Bootstrap Confidence Interval Analysis.
Strictly implements SPEC.md Section 7.4, 8.2, 11 (Phase 6).
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """Calculate exact p50, p90, p95, p99, min, max, mean, and std.
    Input values should be in milliseconds.
    """
    if not values:
        return {
            "count": 0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "mean_ms": 0.0,
            "std_ms": 0.0,
            "p50_ms": 0.0,
            "p90_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
        }

    arr = np.array(values, dtype=np.float64)
    # Using 'linear' method as recommended in statistical standards
    return {
        "count": len(values),
        "min_ms": round(float(np.min(arr)), 3),
        "max_ms": round(float(np.max(arr)), 3),
        "mean_ms": round(float(np.mean(arr)), 3),
        "std_ms": round(float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0, 3),
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p90_ms": round(float(np.percentile(arr, 90)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "p99_ms": round(float(np.percentile(arr, 99)), 3),
    }


def paired_bootstrap_ci(
    pg_medians: List[float],
    mongo_medians: List[float],
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Calculate 95% Confidence Interval for the difference in repeat medians (PG - Mongo).
    Implements SPEC.md Section 7.4.
    """
    n_pairs = min(len(pg_medians), len(mongo_medians))
    if n_pairs == 0:
        return {
            "n_pairs": 0,
            "diff_median_ms": 0.0,
            "ci_95_lower_ms": 0.0,
            "ci_95_upper_ms": 0.0,
            "note": "No paired data available",
        }

    diffs = np.array([pg_medians[i] - mongo_medians[i] for i in range(n_pairs)], dtype=np.float64)
    observed_diff = float(np.median(diffs))

    if n_pairs < 5:
        # Exploratory warning per SPEC Section 7.4
        return {
            "n_pairs": n_pairs,
            "diff_median_ms": round(observed_diff, 3),
            "ci_95_lower_ms": round(float(np.min(diffs)), 3),
            "ci_95_upper_ms": round(float(np.max(diffs)), 3),
            "note": "CI thăm dò (số repeat < 5, khoảng tin cậy không mang tính khẳng định)",
        }

    rng = np.random.default_rng(seed)
    boot_diffs = []
    for _ in range(n_bootstrap):
        sample_indices = rng.integers(0, n_pairs, size=n_pairs)
        boot_diffs.append(np.median(diffs[sample_indices]))

    ci_lower = float(np.percentile(boot_diffs, 2.5))
    ci_upper = float(np.percentile(boot_diffs, 97.5))

    return {
        "n_pairs": n_pairs,
        "diff_median_ms": round(observed_diff, 3),
        "ci_95_lower_ms": round(ci_lower, 3),
        "ci_95_upper_ms": round(ci_upper, 3),
        "note": "95% Bootstrap Confidence Interval",
    }


def analyze_experiment_samples(experiment_dir: Path) -> Dict[str, Any]:
    """Parse raw samples.jsonl and calculate aggregated metrics per engine, query, and repeat.
    Strictly derives all statistics from the raw data.
    """
    samples_file = experiment_dir / "samples.jsonl"
    manifest_file = experiment_dir / "manifest.json"
    summary_file = experiment_dir / "summary.json"

    if not samples_file.exists():
        return {"error": f"samples.jsonl not found in {experiment_dir}"}

    # Fast O(1) cache check if summary.json exists and is fresher than samples.jsonl
    if summary_file.exists():
        try:
            if summary_file.stat().st_mtime >= samples_file.stat().st_mtime:
                with open(summary_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass

    manifest = {}
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    # Structure to hold latencies: engine -> query -> repeat -> list of latency_ms
    # Also separate errors
    raw_data: Dict[str, Dict[str, Dict[int, List[float]]]] = {
        "postgresql": {},
        "mongodb": {},
    }
    error_counts: Dict[str, Dict[str, int]] = {
        "postgresql": {},
        "mongodb": {},
    }
    total_counts: Dict[str, Dict[str, int]] = {
        "postgresql": {},
        "mongodb": {},
    }
    time_bounds: Dict[str, Dict[str, Dict[str, float]]] = {
        "postgresql": {},
        "mongodb": {},
    }

    with open(samples_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except Exception:
                continue

            engine = sample.get("engine", "").lower()
            query = sample.get("query_id", "")
            repeat = sample.get("repeat_id", sample.get("repeat", 1))
            is_warmup = sample.get("is_warmup", False)
            success = sample.get("success", True)
            latency_ms = sample.get("duration_ms", sample.get("latency_ms", 0.0))

            # Never include warm-up samples in statistical analysis
            if is_warmup or not engine or not query:
                continue

            if engine not in raw_data:
                raw_data[engine] = {}
                error_counts[engine] = {}
                total_counts[engine] = {}
                time_bounds[engine] = {}

            if query not in raw_data[engine]:
                raw_data[engine][query] = {}
                error_counts[engine][query] = 0
                total_counts[engine][query] = 0
                time_bounds[engine][query] = {"total_latency_ms": 0.0}

            if repeat not in raw_data[engine][query]:
                raw_data[engine][query][repeat] = []

            total_counts[engine][query] += 1
            if not success:
                error_counts[engine][query] += 1
            else:
                raw_data[engine][query][repeat].append(latency_ms)
                time_bounds[engine][query]["total_latency_ms"] += latency_ms

    # Aggregate metrics
    summary_by_query: Dict[str, Any] = {}
    all_queries = sorted(list(set(list(raw_data.get("postgresql", {}).keys()) + list(raw_data.get("mongodb", {}).keys()))))

    for q in all_queries:
        summary_by_query[q] = {}
        pg_repeat_medians = []
        mongo_repeat_medians = []

        for engine in ["postgresql", "mongodb"]:
            engine_repeats = raw_data.get(engine, {}).get(q, {})
            all_engine_latencies = []
            repeat_stats = []

            for rep in sorted(engine_repeats.keys()):
                rep_lats = engine_repeats[rep]
                all_engine_latencies.extend(rep_lats)
                if rep_lats:
                    med = float(np.median(rep_lats))
                    repeat_stats.append({
                        "repeat": rep,
                        "count": len(rep_lats),
                        "median_ms": round(med, 3),
                        "p95_ms": round(float(np.percentile(rep_lats, 95)), 3),
                    })
                    if engine == "postgresql":
                        pg_repeat_medians.append(med)
                    else:
                        mongo_repeat_medians.append(med)

            overall_perc = calculate_percentiles(all_engine_latencies)
            total = total_counts.get(engine, {}).get(q, 0)
            errs = error_counts.get(engine, {}).get(q, 0)
            error_rate = round((errs / total * 100.0), 2) if total > 0 else 0.0

            # Calculate Throughput (QPS)
            tot_lat_s = (time_bounds.get(engine, {}).get(q, {}).get("total_latency_ms", 0.0)) / 1000.0
            qps = round(len(all_engine_latencies) / tot_lat_s, 2) if tot_lat_s > 0 else 0.0

            summary_by_query[q][engine] = {
                **overall_perc,
                "total_requests": total,
                "error_count": errs,
                "error_rate_pct": error_rate,
                "throughput_qps": qps,
                "repeat_stats": repeat_stats,
            }

        # Bootstrap comparison between PG and MongoDB
        bootstrap_res = paired_bootstrap_ci(pg_repeat_medians, mongo_repeat_medians)
        summary_by_query[q]["comparison"] = {
            "paired_bootstrap": bootstrap_res,
            "speedup_factor": round(
                (summary_by_query[q]["mongodb"]["p50_ms"] / summary_by_query[q]["postgresql"]["p50_ms"]), 2
            ) if summary_by_query[q]["postgresql"]["p50_ms"] > 0 and summary_by_query[q]["mongodb"]["p50_ms"] > 0 else None,
        }

    result = {
        "experiment_id": manifest.get("experiment_id", experiment_dir.name),
        "created_at_utc": manifest.get("created_at_utc"),
        "status": manifest.get("status"),
        "config": manifest.get("config", {}),
        "queries": summary_by_query,
    }

    # Cache calculated summary for subsequent O(1) response time
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass

    return result
