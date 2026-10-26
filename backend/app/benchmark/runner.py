"""Benchmark Runner Engine implementing Mode L (Latency) and Mode T (Throughput).
Strictly implements SPEC.md Section 7, Section 8, and Section 12 (BENCH-01 -> BENCH-11):
- Mode L: Sequential fixed-count execution (C=1).
- Mode T: Multi-worker closed-loop concurrent execution (C in {1, 8, 32}) with strict deadline,
  drain window, and true wall-clock duration accounting.
- High-resolution monotonic timing around DB execution + fetch only.
- Strict isolation of warm-up phase, background resource monitoring, and parameter pool stability.
- Dry-run capability calculating full matrix cell count and estimated duration.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
import random
import time
from typing import Any, Callable, Dict, List, Literal, Optional

from app.adapters import BaseAdapter, get_adapter
from app.benchmark.lock import JobState, global_experiment_lock
from app.benchmark.protocol import BenchmarkProtocol
from app.benchmark.recorder import BenchmarkRecorder, SampleRecord
from app.benchmark.timer import MonotonicTimer
from app.domain.query_catalog import generate_parameter_pool
from configs.indexes import apply_indexes_postgres, apply_indexes_mongo
from configs.profiles import load_profile


@dataclass
class BenchmarkConfig:
    experiment_id: str
    mode: Literal["L", "T"] = "L"
    dataset: str = "fixture-seed42"
    profile: str = "fixture"
    index_profile: Literal["I0", "I1"] = "I1"
    queries: List[str] = field(default_factory=lambda: ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7_offset", "Q7_keyset", "Q8_track_a"])
    engines: List[str] = field(default_factory=lambda: ["postgresql", "mongodb"])
    repeats: int = 5
    # Mode L specific:
    fixed_count: int = 1000
    # Mode T specific:
    concurrency: int = 1
    duration_seconds: float = 60.0
    drain_timeout_seconds: float = 30.0
    # Warmup settings:
    warmup_min_requests: int = 100
    warmup_min_duration_s: float = 20.0
    warmup_max_duration_s: float = 120.0
    seed: int = 42

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "mode": self.mode,
            "dataset": self.dataset,
            "profile": self.profile,
            "index_profile": self.index_profile,
            "queries": self.queries,
            "engines": self.engines,
            "repeats": self.repeats,
            "fixed_count": self.fixed_count,
            "concurrency": self.concurrency,
            "duration_seconds": self.duration_seconds,
            "drain_timeout_seconds": self.drain_timeout_seconds,
            "seed": self.seed,
        }


class BenchmarkRunner:
    """Executes benchmark matrix adhering to paired fairness and strict measurement boundaries."""

    def __init__(self, config: BenchmarkConfig, recorder: Optional[BenchmarkRecorder] = None):
        self.config = config
        self.recorder = recorder or BenchmarkRecorder(experiment_id=config.experiment_id)
        self.lock = global_experiment_lock
        self._total_samples_collected = 0

    def dry_run(self) -> Dict[str, Any]:
        """Calculate experiment matrix cells, execution order, and time estimates without running."""
        shuffled_queries = BenchmarkProtocol.get_shuffled_queries(self.config.queries, self.config.seed)
        cells = []
        est_seconds_total = 0.0

        for q in shuffled_queries:
            for rep in range(1, self.config.repeats + 1):
                engine_order = BenchmarkProtocol.get_engine_order(rep)
                # Keep only engines requested in config
                filtered_engines = [e for e in engine_order if e in self.config.engines]
                for eng in filtered_engines:
                    cell_id = f"{q}_{eng}_rep{rep}"
                    if self.config.mode == "L":
                        # Assume ~2ms per query estimate
                        cell_dur = (self.config.fixed_count * 0.002) + self.config.warmup_min_duration_s
                    else:
                        cell_dur = self.config.duration_seconds + self.config.warmup_min_duration_s
                    est_seconds_total += cell_dur
                    cells.append({
                        "cell_id": cell_id,
                        "query_id": q,
                        "engine": eng,
                        "repeat_id": rep,
                        "mode": self.config.mode,
                        "estimated_duration_s": round(cell_dur, 2),
                    })

        return {
            "experiment_id": self.config.experiment_id,
            "mode": self.config.mode,
            "total_cells": len(cells),
            "estimated_duration_minutes": round(est_seconds_total / 60.0, 2),
            "cells": cells,
        }

    def run(self) -> Dict[str, Any]:
        """Execute full benchmark pipeline under global exclusive lock."""
        total_cells = len(self.config.queries) * self.config.repeats * len(self.config.engines)
        # Acquire lock
        if not self.lock.acquire(
            experiment_id=self.config.experiment_id,
            mode=self.config.mode,
            dataset=self.config.dataset,
            index_profile=self.config.index_profile,
            total_cells=total_cells,
            total_repeats=self.config.repeats,
        ):
            raise RuntimeError(f"Cannot run benchmark: another job is currently active or lock is held.")

        self.recorder.start()
        start_wall_time = time.perf_counter()
        terminal_status = JobState.COMPLETED
        failure_error: Optional[str] = None

        try:
            # Synchronize index catalog profile on both engines (I0 vs I1)
            for eng in self.config.engines:
                try:
                    if eng == "postgresql":
                        apply_indexes_postgres(get_adapter("postgresql"), self.config.index_profile)
                    elif eng == "mongodb":
                        apply_indexes_mongo(get_adapter("mongodb"), self.config.index_profile)
                except Exception:
                    pass

            profile_obj = load_profile(self.config.profile)
            shuffled_queries = BenchmarkProtocol.get_shuffled_queries(self.config.queries, self.config.seed)

            # Pre-generate parameter pools for all queries outside timed regions
            param_pools: Dict[str, List[Dict[str, Any]]] = {}
            for q in shuffled_queries:
                param_pools[q] = generate_parameter_pool(
                    query_id=q,
                    profile=profile_obj,
                    seed=self.config.seed,
                    count=max(200, self.config.fixed_count),
                )

            completed_cells = 0

            # Iterate query blocks
            for q_idx, q in enumerate(shuffled_queries):
                if self.lock.is_cancelled():
                    terminal_status = JobState.CANCELLED
                    break

                for rep in range(1, self.config.repeats + 1):
                    if self.lock.is_cancelled():
                        terminal_status = JobState.CANCELLED
                        break

                    pair_id = BenchmarkProtocol.generate_pair_id(self.config.experiment_id, q, rep)
                    engine_order = BenchmarkProtocol.get_engine_order(rep)
                    engines_to_run = [e for e in engine_order if e in self.config.engines]

                    for eng in engines_to_run:
                        if self.lock.is_cancelled():
                            terminal_status = JobState.CANCELLED
                            break

                        run_id = f"{pair_id}_{eng}"
                        step_label = f"Query {q} | Repeat {rep}/{self.config.repeats} | Engine {eng}"
                        progress_pct = (completed_cells / max(1, total_cells)) * 100.0
                        self.lock.update_progress(
                            current_step=step_label,
                            progress_percent=progress_pct,
                            engine=eng,
                            query_id=q,
                            repeat=rep,
                            total_repeats=self.config.repeats,
                            completed_cells=completed_cells,
                            total_cells=total_cells,
                        )

                        adapter = get_adapter(eng)
                        pool = param_pools[q]

                        # 1. Warm-up phase
                        BenchmarkProtocol.execute_warmup(
                            adapter=adapter,
                            query_id=q,
                            params_pool=pool,
                            min_requests=self.config.warmup_min_requests,
                            min_duration_s=self.config.warmup_min_duration_s,
                            max_duration_s=self.config.warmup_max_duration_s,
                            cancel_check=self.lock.is_cancelled,
                        )

                        if self.lock.is_cancelled():
                            terminal_status = JobState.CANCELLED
                            break

                        # 2. Main Measurement phase
                        if self.config.mode == "L":
                            self._run_mode_l(
                                adapter=adapter,
                                run_id=run_id,
                                pair_id=pair_id,
                                repeat_id=rep,
                                query_id=q,
                                params_pool=pool,
                            )
                        else:
                            self._run_mode_t(
                                adapter=adapter,
                                run_id=run_id,
                                pair_id=pair_id,
                                repeat_id=rep,
                                query_id=q,
                                params_pool=pool,
                            )

                        if self.lock.is_cancelled():
                            terminal_status = JobState.CANCELLED
                            break

                        completed_cells += 1
                        progress_pct = (completed_cells / max(1, total_cells)) * 100.0
                        self.lock.update_progress(
                            current_step=f"Hoàn thành {q} ({eng}) [{completed_cells}/{total_cells}]",
                            progress_percent=progress_pct,
                            engine=eng,
                            query_id=q,
                            repeat=rep,
                            total_repeats=self.config.repeats,
                            completed_cells=completed_cells,
                            total_cells=total_cells,
                        )

            if self.lock.is_cancelled():
                terminal_status = JobState.CANCELLED

            # Outside timed regions: collect diagnostic explain plans
            if terminal_status != JobState.CANCELLED:
                for q in shuffled_queries:
                    for eng in self.config.engines:
                        try:
                            adapter = get_adapter(eng)
                            sample_params = param_pools[q][0]
                            exp_res = adapter.explain(q, sample_params)
                            self.recorder.save_explain_plan(eng, q, exp_res.to_dict())
                        except Exception:
                            pass

        except Exception as ex:
            terminal_status = JobState.FAILED
            failure_error = str(ex)
            raise
        finally:
            if self.lock.is_cancelled():
                terminal_status = JobState.CANCELLED
            self.recorder.stop()
            self.recorder.write_manifest(
                experiment_config=self.config.to_dict(),
                status=terminal_status,
                total_samples=self._total_samples_collected,
                error=failure_error,
            )
            self.lock.release(final_status=terminal_status, error=failure_error)

        total_wall_elapsed = time.perf_counter() - start_wall_time
        return {
            "experiment_id": self.config.experiment_id,
            "status": terminal_status,
            "total_samples": self._total_samples_collected,
            "wall_elapsed_seconds": round(total_wall_elapsed, 2),
            "error": failure_error,
        }

    def _run_mode_l(
        self,
        adapter: BaseAdapter,
        run_id: str,
        pair_id: str,
        repeat_id: int,
        query_id: str,
        params_pool: List[Dict[str, Any]],
    ) -> None:
        """Mode L: Latency sequential fixed-count measurement (BENCH-04)."""
        count = self.config.fixed_count
        pool_len = len(params_pool)
        track = "B" if "track_b" in query_id else "A"

        for seq in range(count):
            if self.lock.is_cancelled():
                break

            param_idx = seq % pool_len
            params = params_pool[param_idx]
            started_at_str = datetime.now(timezone.utc).isoformat()

            timer = MonotonicTimer()
            success = True
            error_type = None
            is_timeout = False
            row_count = 0

            timer.start()
            try:
                res = adapter.execute(query_id, params, timed=True)
                row_count = res.row_count
                if res.status != "success":
                    success = False
                    error_type = res.error
                    if error_type and ("timeout" in error_type.lower() or "timed out" in error_type.lower()):
                        is_timeout = True
            except Exception as e:
                success = False
                error_type = type(e).__name__
                err_str = str(e).lower()
                if (
                    isinstance(e, TimeoutError)
                    or "timeout" in error_type.lower()
                    or "timeout" in err_str
                    or "timed out" in err_str
                ):
                    is_timeout = True
            finally:
                timing = timer.stop()

            sample = SampleRecord(
                run_id=run_id,
                pair_id=pair_id,
                repeat_id=repeat_id,
                engine=adapter.engine_name,
                model_track=track,
                dataset_id=self.config.dataset,
                index_profile=self.config.index_profile,
                query_id=query_id,
                parameter_id=param_idx,
                worker_id=0,
                sequence_no=seq,
                started_at_utc=started_at_str,
                duration_ns=timing.duration_ns,
                duration_ms=timing.duration_ms,
                success=success,
                error_type=error_type,
                timeout=is_timeout,
                cancelled=self.lock.is_cancelled(),
                row_count=row_count,
            )
            self.recorder.record_sample(sample)
            self._total_samples_collected += 1

    def _run_mode_t(
        self,
        adapter: BaseAdapter,
        run_id: str,
        pair_id: str,
        repeat_id: int,
        query_id: str,
        params_pool: List[Dict[str, Any]],
    ) -> None:
        """Mode T: Throughput multi-worker closed-loop concurrent measurement (BENCH-05, BENCH-06)."""
        concurrency = max(1, self.config.concurrency)
        duration_s = self.config.duration_seconds
        drain_timeout_s = self.config.drain_timeout_seconds
        pool_len = len(params_pool)
        track = "B" if "track_b" in query_id else "A"

        start_time = time.perf_counter()
        deadline_time = start_time + duration_s

        def worker_loop(worker_id: int) -> int:
            worker_adapter = get_adapter(adapter.engine_name)
            worker_adapter.prepare()
            seq = 0

            while time.perf_counter() < deadline_time and not self.lock.is_cancelled():
                param_idx = (worker_id * 10000 + seq) % pool_len
                params = params_pool[param_idx]
                started_at_str = datetime.now(timezone.utc).isoformat()

                timer = MonotonicTimer()
                success = True
                error_type = None
                is_timeout = False
                row_count = 0

                timer.start()
                try:
                    res = worker_adapter.execute(query_id, params, timed=True)
                    row_count = res.row_count
                    if res.status != "success":
                        success = False
                        error_type = res.error
                        if error_type and ("timeout" in error_type.lower() or "timed out" in error_type.lower()):
                            is_timeout = True
                except Exception as e:
                    success = False
                    error_type = type(e).__name__
                    err_str = str(e).lower()
                    if (
                        isinstance(e, TimeoutError)
                        or "timeout" in error_type.lower()
                        or "timeout" in err_str
                        or "timed out" in err_str
                    ):
                        is_timeout = True
                finally:
                    timing = timer.stop()

                sample = SampleRecord(
                    run_id=run_id,
                    pair_id=pair_id,
                    repeat_id=repeat_id,
                    engine=adapter.engine_name,
                    model_track=track,
                    dataset_id=self.config.dataset,
                    index_profile=self.config.index_profile,
                    query_id=query_id,
                    parameter_id=param_idx,
                    worker_id=worker_id,
                    sequence_no=seq,
                    started_at_utc=started_at_str,
                    duration_ns=timing.duration_ns,
                    duration_ms=timing.duration_ms,
                    success=success,
                    error_type=error_type,
                    timeout=is_timeout,
                    cancelled=self.lock.is_cancelled(),
                    row_count=row_count,
                )
                self.recorder.record_sample(sample)
                self._total_samples_collected += 1
                seq += 1

            worker_adapter.close()
            return seq

        # Multi-worker closed-loop dispatch
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker_loop, w_id) for w_id in range(concurrency)]
            for fut in as_completed(futures, timeout=duration_s + drain_timeout_s + 10.0):
                fut.result()
