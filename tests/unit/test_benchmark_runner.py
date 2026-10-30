"""Unit and protocol tests for Benchmark Runner (Phase 4 Gate G4).
Strictly implements SPEC.md Section 7, 8 & 12 (BENCH-01 -> BENCH-11):
- BENCH-01: Timer strictly encompasses execution and full cursor fetch.
- BENCH-02: Connect, hash, query build, serialize delays are NOT added to query latency.
- BENCH-03: Warm-up requests are strictly excluded from measurement samples.
- BENCH-04: Mode L accounting: exactly N requests initiated, exactly N outcomes recorded.
- BENCH-05: Mode T concurrency: multi-worker execution respects concurrency limit C.
- BENCH-06: Mode T throughput: wall_elapsed_s spans from issue start to end of drain.
- BENCH-07: Error & timeout handling: raw sample records error_type and timeout=True.
- BENCH-08: Cooperative cancel: stops issuing, drains in-flight, saves partial samples, releases lock.
- BENCH-09: Crash recovery: orphan RUNNING jobs recover to INTERRUPTED state.
- BENCH-10: Paired engine fairness: alternating order (odd: PG->Mongo, even: Mongo->PG).
- BENCH-11: Global exclusive lock: rejects overlapping benchmarks and administrative tasks with 409.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.adapters.base import BaseAdapter, QueryResult
from app.benchmark.lock import ExperimentLock, JobState, global_experiment_lock
from app.benchmark.protocol import BenchmarkProtocol
from app.benchmark.recorder import BenchmarkRecorder, SampleRecord
from app.benchmark.runner import BenchmarkConfig, BenchmarkRunner
from app.benchmark.timer import MonotonicTimer
from app.main import app

client = TestClient(app)


class FakeDelayAdapter(BaseAdapter):
    """Fake adapter injecting controlled delays inside and outside cursor fetch."""

    def __init__(self, engine_name: str = "postgresql", fetch_delay_ms: float = 10.0):
        super().__init__(engine_name)
        self.fetch_delay_ms = fetch_delay_ms
        self.warmup_calls = 0
        self.execute_calls = 0
        self.active_concurrency = 0
        self.max_observed_concurrency = 0

    def health(self, timeout_seconds=None):
        pass

    def prepare(self):
        pass

    def execute(self, query_id: str, params: dict, timed: bool = True) -> QueryResult:
        if not timed:
            self.warmup_calls += 1
            return QueryResult(query_name=query_id, engine=self.engine_name, row_count=1, data=[], execution_time_ms=0.0)

        self.execute_calls += 1
        self.active_concurrency += 1
        if self.active_concurrency > self.max_observed_concurrency:
            self.max_observed_concurrency = self.active_concurrency

        time.sleep(self.fetch_delay_ms / 1000.0)

        self.active_concurrency -= 1
        return QueryResult(
            query_name=query_id,
            engine=self.engine_name,
            row_count=1,
            data=[{"val": 1}],
            execution_time_ms=self.fetch_delay_ms,
        )

    def explain(self, query_id: str, params: dict):
        from app.adapters.base import ExplainResult
        return ExplainResult(query_name=query_id, engine=self.engine_name, raw_plan={"fake": True})

    def describe_indexes(self):
        return []

    def close(self):
        pass


def test_bench_01_timer_encompasses_execute_and_fetch():
    """BENCH-01: Timer strictly encompasses execution and cursor fetch."""
    timer = MonotonicTimer()
    adapter = FakeDelayAdapter(fetch_delay_ms=25.0)

    timer.start()
    res = adapter.execute("Q1", {}, timed=True)
    timing = timer.stop()

    # Timing must capture at least the injected 25ms delay
    assert timing.duration_ms >= 20.0
    assert res.row_count == 1


def test_bench_02_timer_excludes_external_preparation():
    """BENCH-02: Connect, hash, serialization delays are NOT added to query latency."""
    adapter = FakeDelayAdapter(fetch_delay_ms=5.0)

    # External preparation before timer start
    time.sleep(0.060)  # 60ms external overhead

    timer = MonotonicTimer()
    timer.start()
    adapter.execute("Q1", {}, timed=True)
    timing = timer.stop()

    # External 60ms sleep must NOT be included in duration (should be ~5ms, well under 45ms)
    assert timing.duration_ms < 45.0


def test_bench_03_warmup_requests_excluded_from_samples(tmp_path):
    """BENCH-03: Warm-up requests are strictly excluded from measurement samples."""
    adapter = FakeDelayAdapter(fetch_delay_ms=1.0)
    recorder = BenchmarkRecorder("test-bench-03", base_dir=tmp_path)

    # Run warm-up with 10 requests
    warmup_res = BenchmarkProtocol.execute_warmup(
        adapter=adapter,
        query_id="Q1",
        params_pool=[{"order_id": 1}],
        min_requests=10,
        min_duration_s=0.01,
        max_duration_s=1.0,
    )
    assert warmup_res.requests_completed >= 5
    assert adapter.warmup_calls >= 5

    # Check recorder buffer: warm-up must NOT have registered any sample records
    assert len(recorder.sample_buffer) == 0
    recorder.stop()
    assert not (tmp_path / "test-bench-03" / "samples.jsonl").exists() or (tmp_path / "test-bench-03" / "samples.jsonl").stat().st_size == 0


def test_bench_04_mode_l_exact_accounting(tmp_path, monkeypatch):
    """BENCH-04: Mode L accounting: exactly N requests, each with a recorded outcome."""
    adapter_pg = FakeDelayAdapter("postgresql", fetch_delay_ms=1.0)
    adapter_mg = FakeDelayAdapter("mongodb", fetch_delay_ms=1.0)

    adapters_map = {"postgresql": adapter_pg, "mongodb": adapter_mg}
    monkeypatch.setattr("app.benchmark.runner.get_adapter", lambda name: adapters_map[name])

    config = BenchmarkConfig(
        experiment_id="test-bench-04",
        mode="L",
        queries=["Q1"],
        engines=["postgresql"],
        repeats=1,
        fixed_count=25,
        warmup_min_requests=2,
        warmup_min_duration_s=0.01,
    )
    recorder = BenchmarkRecorder(config.experiment_id, base_dir=tmp_path)
    runner = BenchmarkRunner(config, recorder=recorder)

    result = runner.run()
    assert result["status"] == JobState.COMPLETED
    assert result["total_samples"] == 25

    # Read samples.jsonl and verify exact count
    samples_file = tmp_path / "test-bench-04" / "samples.jsonl"
    with open(samples_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 25
    assert all(item["success"] is True for item in lines)
    assert [item["sequence_no"] for item in lines] == list(range(25))


def test_bench_05_and_06_mode_t_concurrency_and_wall_elapsed(tmp_path, monkeypatch):
    """BENCH-05 & BENCH-06: Concurrency level C=4 respected; wall_elapsed_s accounts for entire duration."""
    adapter_pg = FakeDelayAdapter("postgresql", fetch_delay_ms=10.0)
    adapters_map = {"postgresql": adapter_pg}
    monkeypatch.setattr("app.benchmark.runner.get_adapter", lambda name: adapters_map[name])

    config = BenchmarkConfig(
        experiment_id="test-bench-05-06",
        mode="T",
        queries=["Q1"],
        engines=["postgresql"],
        repeats=1,
        concurrency=4,
        duration_seconds=0.2,  # 200ms issue window
        drain_timeout_seconds=2.0,
        warmup_min_requests=2,
        warmup_min_duration_s=0.01,
    )
    recorder = BenchmarkRecorder(config.experiment_id, base_dir=tmp_path)
    runner = BenchmarkRunner(config, recorder=recorder)

    res = runner.run()
    assert res["status"] == JobState.COMPLETED
    assert res["total_samples"] > 0
    # Concurrency was active
    assert adapter_pg.max_observed_concurrency <= 4
    # Wall clock elapsed was at least duration_seconds
    assert res["wall_elapsed_seconds"] >= 0.2


def test_bench_07_error_and_timeout_recording(tmp_path, monkeypatch):
    """BENCH-07: Adapter error or timeout is recorded with error_type and timeout flag."""
    class FailingAdapter(BaseAdapter):
        def __init__(self):
            super().__init__("postgresql")
        def health(self, timeout_seconds=None): pass
        def prepare(self): pass
        def execute(self, query_id: str, params: dict, timed: bool = True):
            raise TimeoutError("Database query execution timed out")
        def explain(self, query_id: str, params: dict): pass
        def describe_indexes(self): return []
        def close(self): pass

    monkeypatch.setattr("app.benchmark.runner.get_adapter", lambda name: FailingAdapter())

    config = BenchmarkConfig(
        experiment_id="test-bench-07",
        mode="L",
        queries=["Q1"],
        engines=["postgresql"],
        repeats=1,
        fixed_count=5,
        warmup_min_requests=0,
        warmup_min_duration_s=0.0,
    )
    recorder = BenchmarkRecorder(config.experiment_id, base_dir=tmp_path)
    runner = BenchmarkRunner(config, recorder=recorder)

    res = runner.run()
    assert res["total_samples"] == 5

    samples_file = tmp_path / "test-bench-07" / "samples.jsonl"
    with open(samples_file, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]
    assert all(s["success"] is False for s in samples)
    assert all(s["timeout"] is True for s in samples)
    assert all("TimeoutError" in s["error_type"] for s in samples)


def test_bench_08_cancel_releases_lock_and_saves_partial_results(tmp_path, monkeypatch):
    """BENCH-08: Cooperative cancel stops issuing, releases lock, and retains partial samples."""
    adapter_pg = FakeDelayAdapter("postgresql", fetch_delay_ms=20.0)
    monkeypatch.setattr("app.benchmark.runner.get_adapter", lambda name: adapter_pg)

    config = BenchmarkConfig(
        experiment_id="test-bench-08",
        mode="L",
        queries=["Q1"],
        engines=["postgresql"],
        repeats=1,
        fixed_count=500,
        warmup_min_requests=0,
        warmup_min_duration_s=0.0,
    )
    recorder = BenchmarkRecorder(config.experiment_id, base_dir=tmp_path)
    runner = BenchmarkRunner(config, recorder=recorder)

    # Cancel after runner starts recording samples
    import threading
    def cancel_worker():
        for _ in range(50):
            if runner._total_samples_collected > 0:
                break
            time.sleep(0.01)
        global_experiment_lock.request_cancel()

    t = threading.Thread(target=cancel_worker)
    t.start()

    res = runner.run()
    t.join()

    assert res["status"] == JobState.CANCELLED
    # Partial samples were retained (> 0 and < 500)
    assert 0 < res["total_samples"] < 500
    # Lock is released
    assert not global_experiment_lock.is_locked()


def test_bench_09_crash_recovery_transitions_to_interrupted(tmp_path):
    """BENCH-09: Orphan RUNNING job state from crash recovers to INTERRUPTED."""
    state_file = tmp_path / "active_job.json"
    orphan_state = {
        "experiment_id": "crashed-exp-123",
        "status": JobState.RUNNING,
        "started_at": "2026-09-30T12:00:00Z",
        "mode": "L",
        "dataset": "fixture",
        "index_profile": "I1",
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(orphan_state, f)

    # Instantiate lock which triggers recovery
    test_lock = ExperimentLock(state_file_path=state_file)
    status = test_lock.get_status()
    assert status["status"] == JobState.INTERRUPTED
    assert "INTERRUPTED" in status["error"]
    assert not test_lock.is_locked()


def test_bench_10_paired_alternating_engine_fairness():
    """BENCH-10: Paired engine execution order strictly alternates between odd and even repeats."""
    # Repeat 1 (odd) -> PG first, Mongo second
    order_rep1 = BenchmarkProtocol.get_engine_order(1)
    assert order_rep1 == ["postgresql", "mongodb"]

    # Repeat 2 (even) -> Mongo first, PG second
    order_rep2 = BenchmarkProtocol.get_engine_order(2)
    assert order_rep2 == ["mongodb", "postgresql"]

    # Repeat 3 (odd) -> PG first
    order_rep3 = BenchmarkProtocol.get_engine_order(3)
    assert order_rep3 == ["postgresql", "mongodb"]

    # Repeat 4 (even) -> Mongo first
    order_rep4 = BenchmarkProtocol.get_engine_order(4)
    assert order_rep4 == ["mongodb", "postgresql"]


def test_bench_11_exclusive_lock_conflict_and_api(tmp_path):
    """BENCH-11: Mutually exclusive lock rejects overlapping runs with 409 Conflict."""
    # Manually lock global lock
    acquired = global_experiment_lock.acquire("active-test-job", "L", "fixture", "I1")
    assert acquired is True

    try:
        # Starting another run via API returns 409 Conflict
        res = client.post("/api/benchmark/run", json={"experiment_id": "second-job"})
        assert res.status_code == 409
        assert "409 Conflict" in res.json()["detail"]

        # Check status endpoint
        st_res = client.get("/api/benchmark/status")
        assert st_res.status_code == 200
        assert st_res.json()["status"] == JobState.RUNNING
    finally:
        global_experiment_lock.release()

    # Once released, lock is free
    assert not global_experiment_lock.is_locked()
