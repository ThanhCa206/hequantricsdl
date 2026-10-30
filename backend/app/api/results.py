"""API Router for Benchmark Results, Statistical Analysis, and Exporting.
Strictly implements SPEC.md Section 8, 10.5, 10.7 (Gate G5 & G6).
"""

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.reports.statistics import analyze_experiment_samples
from app.reports.exporter import generate_markdown_report, generate_csv_summary

router = APIRouter(prefix="/results", tags=["Results & Analysis"])


def _get_safe_exp_dir(experiment_id: str, base_dir: Optional[str] = None) -> Path:
    """Validate experiment_id against path traversal attacks (SPEC Section 12)."""
    if not re.match(r"^[a-zA-Z0-9_\-]+$", experiment_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid experiment ID '{experiment_id}': only alphanumeric characters, dashes, and underscores allowed.",
        )
    base_path = Path(base_dir or get_settings().results_dir).resolve()
    target_path = (base_path / experiment_id).resolve()
    if not str(target_path).startswith(str(base_path)):
        raise HTTPException(status_code=400, detail="Path traversal attempt detected.")
    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return target_path


@router.get("/{experiment_id}/summary")
def get_experiment_summary(experiment_id: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Calculate and return full statistical summary (p50..p99, QPS, bootstrap CI)."""
    exp_dir = _get_safe_exp_dir(experiment_id, base_dir)
    summary = analyze_experiment_samples(exp_dir)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@router.get("/{experiment_id}/resources")
def get_experiment_resources(experiment_id: str, base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve time-series CPU and RAM resource metrics."""
    exp_dir = _get_safe_exp_dir(experiment_id, base_dir)
    res_file = exp_dir / "resources.csv"
    if not res_file.exists():
        return []
    
    metrics = []
    with open(res_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                metrics.append({
                    "timestamp_utc": row["timestamp_utc"],
                    "cpu_percent": float(row["cpu_percent"]),
                    "memory_mb": float(row["memory_mb"]),
                })
            except Exception:
                continue
    return metrics


@router.get("/{experiment_id}/plans")
def get_experiment_plans(experiment_id: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve execution plans collected after the experiment."""
    exp_dir = _get_safe_exp_dir(experiment_id, base_dir)
    plans_dir = exp_dir / "plans"
    if not plans_dir.exists():
        return {}
    
    plans: Dict[str, Any] = {}
    for plan_file in plans_dir.glob("*.json"):
        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                plans[plan_file.stem] = json.load(f)
        except Exception:
            pass
    return plans


@router.get("/{experiment_id}/export/markdown", response_class=PlainTextResponse)
def export_markdown(experiment_id: str, base_dir: Optional[str] = None):
    """Export formatted Markdown report."""
    exp_dir = _get_safe_exp_dir(experiment_id, base_dir)
    summary = analyze_experiment_samples(exp_dir)
    return generate_markdown_report(summary)


@router.get("/{experiment_id}/export/csv", response_class=PlainTextResponse)
def export_csv(experiment_id: str, base_dir: Optional[str] = None):
    """Export CSV summary data."""
    exp_dir = _get_safe_exp_dir(experiment_id, base_dir)
    summary = analyze_experiment_samples(exp_dir)
    return generate_csv_summary(summary)
