"""API Router for Benchmark Job Coordination, Execution, Progress, and Cancel.
Strictly implements SPEC.md Section 7, Section 9 (Gate G4).
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.benchmark.lock import JobState, global_experiment_lock
from app.benchmark.runner import BenchmarkConfig, BenchmarkRunner

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


class BenchmarkRunRequest(BaseModel):
    experiment_id: str = Field(..., description="Unique experiment ID (e.g. E0-smoke-fixture)")
    mode: Literal["L", "T"] = Field("L", description="Mode L (latency) or Mode T (throughput)")
    dataset: str = Field("fixture-seed42", description="Dataset identifier")
    profile: str = Field("fixture", description="Profile name (fixture, small, medium, large)")
    index_profile: Literal["I0", "I1"] = Field("I1", description="Index catalog configuration (I0 or I1)")
    queries: List[str] = Field(default_factory=lambda: ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7_offset", "Q7_keyset", "Q8_track_a"])
    engines: List[str] = Field(default_factory=lambda: ["postgresql", "mongodb"])
    repeats: int = Field(5, ge=1, le=20, description="Number of paired repeats")
    fixed_count: int = Field(1000, ge=1, le=100000, description="Fixed request count for Mode L")
    concurrency: int = Field(1, ge=1, le=128, description="Concurrency level for Mode T")
    duration_seconds: float = Field(60.0, ge=1.0, le=3600.0, description="Issue duration for Mode T")
    warmup_min_requests: int = Field(100, ge=0, description="Minimum warm-up requests")
    warmup_min_duration_s: float = Field(20.0, ge=0.0, description="Minimum warm-up duration")
    seed: int = Field(42, description="Deterministic random seed")


def _execute_runner_in_background(config: BenchmarkConfig):
    runner = BenchmarkRunner(config)
    try:
        runner.run()
    except Exception:
        pass


@router.get("/status")
def get_benchmark_status():
    """Retrieve active benchmark lock, running state, and current step progress."""
    return global_experiment_lock.get_status()


@router.post("/dry-run")
def dry_run_benchmark(request: BenchmarkRunRequest):
    """Estimate cells count and duration without running actual benchmark."""
    config = BenchmarkConfig(**request.dict())
    runner = BenchmarkRunner(config)
    return runner.dry_run()


@router.post("/run")
def start_benchmark_run(request: BenchmarkRunRequest):
    """Initiate a benchmark experiment in the background under global lock."""
    # Check if already locked (BENCH-11)
    if global_experiment_lock.is_locked():
        raise HTTPException(
            status_code=409,
            detail="Another benchmark or administrative operation is currently running. Request rejected (409 Conflict).",
        )

    config = BenchmarkConfig(**request.dict())
    t = threading.Thread(target=_execute_runner_in_background, args=(config,), daemon=True)
    t.start()

    return {
        "message": f"Benchmark experiment '{request.experiment_id}' started successfully.",
        "experiment_id": request.experiment_id,
        "mode": request.mode,
        "status": JobState.RUNNING,
    }


@router.post("/cancel")
def cancel_active_benchmark():
    """Request graceful cooperative cancellation of active benchmark (BENCH-08)."""
    success = global_experiment_lock.request_cancel()
    if not success:
        return {"message": "No active benchmark running to cancel.", "cancelled": False}
    return {"message": "Cancellation request submitted. Draining in-flight requests...", "cancelled": True}


@router.get("/experiments")
def list_experiments(base_dir: str = "results"):
    """List historical experiment directories and their manifest status."""
    res_path = Path(base_dir)
    if not res_path.exists():
        return []

    experiments = []
    for exp_dir in sorted(res_path.iterdir()):
        if exp_dir.is_dir() and (exp_dir / "manifest.json").exists():
            try:
                with open(exp_dir / "manifest.json", "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                experiments.append({
                    "experiment_id": manifest.get("experiment_id", exp_dir.name),
                    "created_at_utc": manifest.get("created_at_utc"),
                    "status": manifest.get("status"),
                    "total_samples": manifest.get("total_samples", 0),
                    "config": manifest.get("config", {}),
                })
            except Exception:
                pass
    return experiments


@router.get("/experiments/{experiment_id}")
def get_experiment_manifest(experiment_id: str, base_dir: str = "results"):
    """Retrieve full manifest.json for a given experiment ID."""
    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+$", experiment_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid experiment ID '{experiment_id}': disallowed characters.",
        )
    base_path = Path(base_dir).resolve()
    target_path = (base_path / experiment_id).resolve()
    if not str(target_path).startswith(str(base_path)):
        raise HTTPException(status_code=400, detail="Path traversal attempt detected.")
    manifest_path = target_path / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
