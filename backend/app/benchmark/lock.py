"""Global Exclusive Lock and State Coordination for Benchmark Execution.
Strictly implements SPEC.md Section 7.6, 9.2, and BENCH-08, BENCH-09, BENCH-11:
- Enforces mutual exclusion: exactly one experiment/import/indexing task at a time.
- Returns 409 Conflict when an operation is requested while a benchmark is running.
- Supports graceful cooperative cancellation (BENCH-08) without deadlock.
- Recovers from abrupt process crashes (BENCH-09): transitions orphan RUNNING jobs to INTERRUPTED.
"""

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class JobState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


@dataclass
class ActiveJobInfo:
    experiment_id: str
    status: str
    started_at: str
    mode: str
    dataset: str
    index_profile: str
    current_step: str = ""
    progress_percent: float = 0.0
    error: Optional[str] = None
    engine: Optional[str] = None
    query_id: Optional[str] = None
    repeat: int = 0
    total_repeats: int = 1
    completed_cells: int = 0
    total_cells: int = 0


class ExperimentLock:
    """Process-wide and filesystem-backed mutually exclusive benchmark lock."""

    def __init__(self, state_file_path: Optional[Path] = None):
        self._thread_lock = threading.RLock()
        self._cancel_event = threading.Event()
        self.state_file = state_file_path or Path("results") / "active_job.json"
        self._active_job: Optional[ActiveJobInfo] = None
        self._recover_state_on_startup()

    def _recover_state_on_startup(self) -> None:
        """BENCH-09: Recover crashed orphan jobs on startup.
        If a previous process died while RUNNING, mark as INTERRUPTED.
        """
        try:
            if self.state_file.exists():
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") in (JobState.RUNNING, JobState.CANCELLING):
                    data["status"] = JobState.INTERRUPTED
                    data["error"] = "Process terminated unexpectedly; job marked INTERRUPTED."
                    with open(self.state_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    self._active_job = ActiveJobInfo(**{k: v for k, v in data.items() if k in ActiveJobInfo.__annotations__})
                elif data.get("status"):
                    self._active_job = ActiveJobInfo(**{k: v for k, v in data.items() if k in ActiveJobInfo.__annotations__})
        except Exception:
            pass

    def _is_locked_internal(self) -> bool:
        return self._active_job is not None and self._active_job.status in (
            JobState.RUNNING,
            JobState.CANCELLING,
        )

    def is_locked(self) -> bool:
        """Check if an experiment is currently occupying the lock."""
        with self._thread_lock:
            return self._is_locked_internal()

    def get_status(self) -> Dict[str, Any]:
        """Return current lock and active job descriptor."""
        with self._thread_lock:
            if self._active_job:
                res = asdict(self._active_job)
                res["is_locked"] = self._is_locked_internal()
                res["active_job_id"] = self._active_job.experiment_id
                res["state"] = self._active_job.status
                res["progress"] = {
                    "engine": self._active_job.engine,
                    "query_id": self._active_job.query_id,
                    "repeat": self._active_job.repeat,
                    "total_repeats": self._active_job.total_repeats,
                    "completed_cells": self._active_job.completed_cells,
                    "total_cells": self._active_job.total_cells,
                    "percent": self._active_job.progress_percent,
                    "step": self._active_job.current_step,
                }
                return res
            return {
                "status": JobState.IDLE,
                "state": JobState.IDLE,
                "is_locked": False,
                "active_job_id": None,
                "progress": {
                    "completed_cells": 0,
                    "total_cells": 0,
                },
            }

    def acquire(
        self,
        experiment_id: str,
        mode: str,
        dataset: str,
        index_profile: str,
        total_cells: int = 0,
        total_repeats: int = 1,
    ) -> bool:
        """Attempt to acquire exclusive lock. Returns False if already locked."""
        with self._thread_lock:
            if self._active_job and self._active_job.status in (
                JobState.RUNNING,
                JobState.CANCELLING,
            ):
                return False

            self._cancel_event.clear()
            self._active_job = ActiveJobInfo(
                experiment_id=experiment_id,
                status=JobState.RUNNING,
                started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                mode=mode,
                dataset=dataset,
                index_profile=index_profile,
                total_cells=total_cells,
                total_repeats=total_repeats,
            )
            self._save_state_file()
            return True

    def update_progress(
        self,
        current_step: str,
        progress_percent: float,
        engine: Optional[str] = None,
        query_id: Optional[str] = None,
        repeat: Optional[int] = None,
        total_repeats: Optional[int] = None,
        completed_cells: Optional[int] = None,
        total_cells: Optional[int] = None,
    ) -> None:
        """Update job progress without altering lock state."""
        with self._thread_lock:
            if self._active_job:
                self._active_job.current_step = current_step
                self._active_job.progress_percent = round(progress_percent, 1)
                if engine is not None:
                    self._active_job.engine = engine
                if query_id is not None:
                    self._active_job.query_id = query_id
                if repeat is not None:
                    self._active_job.repeat = repeat
                if total_repeats is not None:
                    self._active_job.total_repeats = total_repeats
                if completed_cells is not None:
                    self._active_job.completed_cells = completed_cells
                if total_cells is not None:
                    self._active_job.total_cells = total_cells
                self._save_state_file()

    def request_cancel(self) -> bool:
        """Signal cooperative cancellation to running workers (BENCH-08)."""
        with self._thread_lock:
            if not self._active_job or self._active_job.status != JobState.RUNNING:
                return False
            self._active_job.status = JobState.CANCELLING
            self._cancel_event.set()
            self._save_state_file()
            return True

    def is_cancelled(self) -> bool:
        """Check if cancel flag was raised."""
        return self._cancel_event.is_set()

    def release(self, final_status: str = JobState.COMPLETED, error: Optional[str] = None) -> None:
        """Release exclusive lock and persist terminal status."""
        with self._thread_lock:
            if self._active_job:
                self._active_job.status = final_status
                if final_status == JobState.COMPLETED:
                    self._active_job.progress_percent = 100.0
                    if self._active_job.total_cells > 0:
                        self._active_job.completed_cells = self._active_job.total_cells
                    self._active_job.current_step = "Thực nghiệm hoàn tất thành công."
                if error:
                    self._active_job.error = error
                self._save_state_file()
            self._cancel_event.clear()

    def _save_state_file(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            if self._active_job:
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(asdict(self._active_job), f, indent=2)
        except Exception:
            pass


# Global singleton instance
global_experiment_lock = ExperimentLock()
