"""PostgreSQL Adapter implementation using Psycopg 3 with connection pooling.
Conforms to BaseAdapter contract.
"""

import time
from typing import Any, Dict, List, Optional
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.adapters.base import (
    BaseAdapter,
    ExplainResult,
    HealthStatus,
    IndexInfo,
    QueryResult,
)
from app.config import Settings, get_settings


class PostgresAdapter(BaseAdapter):
    """PostgreSQL adapter managing connections, health checks, execution, and plans."""

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(engine_name="postgresql")
        self.settings = settings or get_settings()
        self._pool: Optional[ConnectionPool] = None
        self._pool_size = self.settings.postgres_max_connections

    @property
    def conn_info(self) -> Dict[str, Any]:
        """Return safe (sanitized) connection dictionary."""
        return {
            "host": self.settings.postgres_host,
            "port": self.settings.postgres_port,
            "database": self.settings.postgres_db,
            "user": self.settings.postgres_user,
            "max_connections": self._pool_size,
        }

    def _get_connection_kwargs(self, timeout_seconds: Optional[float] = None) -> Dict[str, Any]:
        timeout = int(timeout_seconds) if timeout_seconds else self.settings.client_timeout_seconds
        return {
            "host": self.settings.postgres_host,
            "port": self.settings.postgres_port,
            "dbname": self.settings.postgres_db,
            "user": self.settings.postgres_user,
            "password": self.settings.postgres_password,
            "connect_timeout": max(1, timeout),
            "autocommit": True,
            "row_factory": dict_row,
        }

    def _ensure_pool(self) -> ConnectionPool:
        if self._pool is None or self._pool.closed:
            conninfo = (
                f"host={self.settings.postgres_host} "
                f"port={self.settings.postgres_port} "
                f"dbname={self.settings.postgres_db} "
                f"user={self.settings.postgres_user} "
                f"password={self.settings.postgres_password} "
                f"connect_timeout={self.settings.client_timeout_seconds}"
            )
            self._pool = ConnectionPool(
                conninfo=conninfo,
                min_size=1,
                max_size=self._pool_size,
                kwargs={"autocommit": True, "row_factory": dict_row},
                open=True,
            )
        return self._pool

    def health(self, timeout_seconds: Optional[float] = 3.0) -> HealthStatus:
        """Ping PostgreSQL, verify version, and record latency in milliseconds."""
        start_time = time.perf_counter()
        try:
            kwargs = self._get_connection_kwargs(timeout_seconds=timeout_seconds)
            with psycopg.connect(**kwargs) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    row = cur.fetchone()
                    version_str = row["version"] if row else None
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return HealthStatus(
                is_healthy=True,
                engine=self.engine_name,
                version=version_str,
                latency_ms=elapsed_ms,
                connection_info=self.conn_info,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return HealthStatus(
                is_healthy=False,
                engine=self.engine_name,
                version=None,
                latency_ms=elapsed_ms,
                connection_info=self.conn_info,
                error=f"PostgreSQL connection error: {str(e)}",
            )

    def prepare(self) -> None:
        """Initialize connection pool and verify acquiring a connection."""
        pool = self._ensure_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")

    def execute(
        self,
        query_id: str,
        params: Dict[str, Any],
        timed: bool = True,
    ) -> QueryResult:
        """Execute SQL query.

        Timed region measures only statement execution and full cursor fetch.
        """
        from app.domain.query_catalog import POSTGRES_QUERIES, normalize_query_output

        pool = self._ensure_pool()
        if query_id in POSTGRES_QUERIES:
            sql = POSTGRES_QUERIES[query_id]
        elif query_id.startswith("live_test") and "sql" in params:
            sql = params["sql"]
        else:
            raise ValueError(f"Query '{query_id}' not found in PostgreSQL catalog.")
        sql_params = params

        with pool.connection() as conn:
            with conn.cursor() as cur:
                if timed:
                    t_start = time.perf_counter_ns()
                    cur.execute(sql, sql_params)
                    rows = cur.fetchall()
                    t_end = time.perf_counter_ns()
                    execution_time_ms = (t_end - t_start) / 1_000_000.0
                else:
                    cur.execute(sql, sql_params)
                    rows = cur.fetchall()
                    execution_time_ms = 0.0

        normalized_rows = normalize_query_output(query_id, rows)

        return QueryResult(
            query_name=query_id,
            engine=self.engine_name,
            row_count=len(normalized_rows),
            data=normalized_rows,
            execution_time_ms=execution_time_ms,
            status="success",
        )

    def explain(
        self,
        query_id: str,
        params: Dict[str, Any],
    ) -> ExplainResult:
        """Run EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) for diagnostics."""
        from app.domain.query_catalog import POSTGRES_QUERIES

        pool = self._ensure_pool()
        if query_id in POSTGRES_QUERIES:
            sql = POSTGRES_QUERIES[query_id]
        elif query_id.startswith("live_test") and "sql" in params:
            sql = params["sql"]
        else:
            raise ValueError(f"Query '{query_id}' not found in PostgreSQL catalog.")
        sql_params = params

        explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(explain_sql, sql_params)
                row = cur.fetchone()
                raw_plan = row[0] if (row and isinstance(row, list)) else (row.get("QUERY PLAN", {}) if isinstance(row, dict) else {})

        # Extract top-level node metrics
        top_node = raw_plan[0].get("Plan", {}) if isinstance(raw_plan, list) and len(raw_plan) > 0 else {}
        scan_type = top_node.get("Node Type")
        index_used = top_node.get("Index Name")
        exec_time = raw_plan[0].get("Execution Time") if isinstance(raw_plan, list) and len(raw_plan) > 0 else None

        return ExplainResult(
            query_name=query_id,
            engine=self.engine_name,
            raw_plan=raw_plan,
            scan_type=scan_type,
            index_used=index_used,
            execution_time_ms=exec_time,
        )

    def describe_indexes(self) -> List[IndexInfo]:
        """Retrieve existing indexes on user tables."""
        pool = self._ensure_pool()
        sql = """
            SELECT
                i.relname AS index_name,
                t.relname AS table_name,
                ix.indisunique AS is_unique,
                pg_relation_size(i.oid) AS size_bytes,
                ARRAY(
                    SELECT pg_get_indexdef(ix.indexrelid, k + 1, true)
                    FROM generate_subscripts(ix.indkey, 1) as k
                    ORDER BY k
                ) AS fields
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relkind = 'r'
            ORDER BY t.relname, i.relname;
        """
        indexes: List[IndexInfo] = []
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        indexes.append(
                            IndexInfo(
                                index_name=row["index_name"],
                                entity_name=row["table_name"],
                                fields=list(row["fields"]) if row["fields"] else [],
                                is_unique=bool(row["is_unique"]),
                                size_bytes=int(row["size_bytes"]) if row["size_bytes"] is not None else None,
                            )
                        )
        except Exception:
            # If tables don't exist yet, return empty list gracefully
            pass
        return indexes

    def close(self) -> None:
        """Close pool connection gracefully."""
        if self._pool is not None and not self._pool.closed:
            self._pool.close()
            self._pool = None
