"""High-resolution monotonic timer for benchmark execution.
Strictly implements SPEC.md Section 7.1, 7.6, and BENCH-01, BENCH-02:
- Uses `time.perf_counter_ns()` for nanosecond precision.
- Timed region strictly bounds cursor execution and cursor fetching into memory.
- Excludes connection establishment, connection pool acquisition, query building,
  serialization, hashing, normalization, progress reporting, and logging.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class TimingMeasurement:
    start_ns: int
    end_ns: int
    duration_ns: int
    duration_ms: float


class MonotonicTimer:
    """Context manager or manual probe measuring only code inside timed window."""

    def __init__(self):
        self.start_ns: Optional[int] = None
        self.end_ns: Optional[int] = None
        self.duration_ns: Optional[int] = None

    def start(self) -> "MonotonicTimer":
        self.start_ns = time.perf_counter_ns()
        self.end_ns = None
        self.duration_ns = None
        return self

    def stop(self) -> TimingMeasurement:
        self.end_ns = time.perf_counter_ns()
        if self.start_ns is None:
            raise RuntimeError("Timer was stopped before being started")
        self.duration_ns = max(0, self.end_ns - self.start_ns)
        return TimingMeasurement(
            start_ns=self.start_ns,
            end_ns=self.end_ns,
            duration_ns=self.duration_ns,
            duration_ms=self.duration_ns / 1_000_000.0,
        )

    def __enter__(self) -> "MonotonicTimer":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.end_ns is None:
            self.stop()
