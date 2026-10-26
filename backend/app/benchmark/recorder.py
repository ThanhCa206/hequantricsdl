"""Raw Sample Recorder, Resource Sampler, and Manifest Generator.
Strictly implements SPEC.md Section 8 & Section 7.1, 7.6:
- Persists immutable experiment artifacts in `results/<experiment_id>/`.
- Streams raw request records into `samples.jsonl` with nanosecond precision.
- Gathers host/container resource utilization into `resources.csv`.
- Compiles comprehensive environment and execution manifest into `manifest.json`.
- Safely flushes buffers and guarantees partial result retention on cancellation or interruption.
"""

import csv
import json
import os
import platform
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SampleRecord:
    run_id: str
    pair_id: str
    repeat_id: int
    engine: str
    model_track: str
    dataset_id: str
    index_profile: str
    query_id: str
    parameter_id: int
    worker_id: int
    sequence_no: int
    started_at_utc: str
    duration_ns: int
    duration_ms: float
    success: bool
    error_type: Optional[str] = None
    timeout: bool = False
    cancelled: bool = False
    row_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResourceMonitor:
    """Background daemon sampling CPU and RAM during experiment execution."""

    def __init__(self, output_csv_path: Path, interval_s: float = 1.0):
        self.output_csv = output_csv_path
        self.interval_s = interval_s
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        # Write CSV header if not exists
        if not self.output_csv.exists():
            with open(self.output_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp_utc", "cpu_percent", "memory_mb"])

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._thread.start()

    def _sampling_loop(self) -> None:
        import psutil
        while not self._stop_event.is_set():
            try:
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().used / (1024 * 1024)

                with open(self.output_csv, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([now_str, round(cpu, 1), round(mem, 1)])
            except Exception:
                pass
            self._stop_event.wait(self.interval_s)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)


class BenchmarkRecorder:
    """Manages raw measurement storage, manifests, and diagnostic plans."""

    def __init__(self, experiment_id: str, base_dir: Optional[Path] = None):
        self.experiment_id = experiment_id
        self.exp_dir = (base_dir or Path("results")) / experiment_id
        self.exp_dir.mkdir(parents=True, exist_ok=True)

        self.samples_file = self.exp_dir / "samples.jsonl"
        self.resources_file = self.exp_dir / "resources.csv"
        self.manifest_file = self.exp_dir / "manifest.json"
        self.plans_dir = self.exp_dir / "plans"
        self.plans_dir.mkdir(exist_ok=True)

        self.sample_buffer: List[SampleRecord] = []
        self._buffer_lock = threading.Lock()
        self.resource_monitor = ResourceMonitor(self.resources_file, interval_s=1.0)

    def start(self) -> None:
        """Start background resource monitoring."""
        self.resource_monitor.start()

    def stop(self) -> None:
        """Stop monitor and flush all remaining samples."""
        self.resource_monitor.stop()
        self.flush()

    def record_sample(self, sample: SampleRecord) -> None:
        """Buffer a completed request attempt."""
        with self._buffer_lock:
            self.sample_buffer.append(sample)
            if len(self.sample_buffer) >= 200:
                self._flush_locked()

    def flush(self) -> None:
        """Force flush all buffered samples to disk."""
        with self._buffer_lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self.sample_buffer:
            return
        with open(self.samples_file, "a", encoding="utf-8") as f:
            for s in self.sample_buffer:
                f.write(json.dumps(s.to_dict()) + "\n")
        self.sample_buffer.clear()

    def save_explain_plan(self, engine: str, query_id: str, plan_dict: Dict[str, Any]) -> None:
        """Store explain plan JSON outside timed region."""
        p_path = self.plans_dir / f"{engine}_{query_id}.json"
        with open(p_path, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2)

    def write_manifest(
        self,
        experiment_config: Dict[str, Any],
        status: str,
        total_samples: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Generate and save complete environment and experiment metadata."""
        git_commit = "unknown"
        git_dirty = False
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                git_commit = res.stdout.strip()
            diff_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=2)
            git_dirty = bool(diff_res.stdout.strip())
        except Exception:
            pass

        manifest_data = {
            "experiment_id": self.experiment_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "error": error,
            "total_samples": total_samples,
            "spec_version": "1.0",
            "git": {
                "commit": git_commit,
                "is_dirty": git_dirty,
            },
            "environment": {
                "os": platform.system(),
                "os_release": platform.release(),
                "cpu_count": os.cpu_count() or 1,
                "python_version": platform.python_version(),
                "container_quota": {
                    "cpus": 2.0,
                    "memory": "2048m",
                },
                "target_versions": {
                    "postgresql": "PostgreSQL 17.2-alpine",
                    "mongodb": "MongoDB 8.0.4",
                },
            },
            "config": experiment_config,
        }

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
