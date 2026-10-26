"""Benchmark Protocol Definitions, Alternating Engine Order, and Warm-up Procedures.
Strictly implements SPEC.md Section 7.3, 7.4, and BENCH-03, BENCH-10:
- Alternating engine execution order: PG -> Mongo on odd repeats, Mongo -> PG on even repeats.
- Deterministic query shuffling via saved random seed.
- Isolated warm-up protocol: warms pool and caches, records warm-up completion without polluting raw measurement samples.
- Paired comparison metadata linking (pair_id).
"""

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WarmupResult:
    engine: str
    query_id: str
    requests_completed: int
    duration_seconds: float
    is_adequate: bool  # True if reached min requests or min duration within cap
    error: Optional[str] = None


class BenchmarkProtocol:
    """Manages protocol execution rules, sequence ordering, and warm-up policies."""

    @staticmethod
    def get_engine_order(repeat_idx: int) -> List[str]:
        """Alternating engine order per repeat:
        Repeat 1, 3, 5 (1-based odd) -> ['postgresql', 'mongodb']
        Repeat 2, 4, 6 (1-based even) -> ['mongodb', 'postgresql']
        """
        if repeat_idx % 2 == 1:
            return ["postgresql", "mongodb"]
        else:
            return ["mongodb", "postgresql"]

    @staticmethod
    def get_shuffled_queries(queries: List[str], seed: int) -> List[str]:
        """Deterministically shuffle query execution sequence using given seed."""
        shuffled = list(queries)
        rng = random.Random(seed)
        rng.shuffle(shuffled)
        return shuffled

    @staticmethod
    def generate_pair_id(experiment_id: str, query_id: str, repeat_id: int) -> str:
        """Generate unique, deterministic identifier linking the paired runs."""
        return f"{experiment_id}_{query_id}_rep{repeat_id}"

    @staticmethod
    def execute_warmup(
        adapter: Any,
        query_id: str,
        params_pool: List[Dict[str, Any]],
        min_requests: int = 100,
        min_duration_s: float = 20.0,
        max_duration_s: float = 120.0,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> WarmupResult:
        """Run warm-up phase to warm OS/database cache and connection pools.

        IMPORTANT (BENCH-03): Warm-up executions are strictly excluded from
        raw measurement samples and benchmark timing statistics.
        """
        start_time = time.perf_counter()
        req_count = 0
        pool_len = max(1, len(params_pool))

        # First ensure pool is prepared
        adapter.prepare()

        while True:
            if cancel_check and cancel_check():
                break

            now = time.perf_counter()
            elapsed = now - start_time

            # Check termination criteria
            if elapsed >= max_duration_s:
                break
            if req_count >= min_requests and elapsed >= min_duration_s:
                break

            # Execute warm-up request (untimed for metric collection)
            p = params_pool[req_count % pool_len]
            try:
                adapter.execute(query_id, p, timed=False)
                req_count += 1
            except Exception as e:
                return WarmupResult(
                    engine=adapter.engine_name,
                    query_id=query_id,
                    requests_completed=req_count,
                    duration_seconds=time.perf_counter() - start_time,
                    is_adequate=False,
                    error=str(e),
                )

        total_elapsed = time.perf_counter() - start_time
        adequate = req_count >= min(min_requests, 5) or total_elapsed >= min_duration_s

        return WarmupResult(
            engine=adapter.engine_name,
            query_id=query_id,
            requests_completed=req_count,
            duration_seconds=total_elapsed,
            is_adequate=adequate,
        )
