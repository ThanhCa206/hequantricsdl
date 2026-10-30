"""MongoDB Adapter implementation using PyMongo.
Conforms to BaseAdapter contract.
"""

import time
from typing import Any, Dict, List, Optional
import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.adapters.base import (
    BaseAdapter,
    ExplainResult,
    HealthStatus,
    IndexInfo,
    QueryResult,
)
from app.config import Settings, get_settings


class MongoAdapter(BaseAdapter):
    """MongoDB adapter managing connection, health, query execution, and explain plans."""

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(engine_name="mongodb")
        self.settings = settings or get_settings()
        self._client: Optional[MongoClient] = None

    @property
    def conn_info(self) -> Dict[str, Any]:
        """Return safe (sanitized) connection dictionary."""
        return {
            "host": self.settings.mongo_host,
            "port": self.settings.mongo_port,
            "database": self.settings.mongo_db,
            "user": self.settings.mongo_initdb_root_username,
            "max_pool_size": self.settings.mongo_max_pool_size,
        }

    def _ensure_client(self, timeout_ms: Optional[int] = None) -> MongoClient:
        if self._client is None:
            effective_timeout = timeout_ms or (self.settings.client_timeout_seconds * 1000)
            self._client = MongoClient(
                host=self.settings.mongo_host,
                port=self.settings.mongo_port,
                username=self.settings.mongo_initdb_root_username,
                password=self.settings.mongo_initdb_root_password,
                authSource="admin",
                maxPoolSize=self.settings.mongo_max_pool_size,
                serverSelectionTimeoutMS=effective_timeout,
                connectTimeoutMS=min(5000, effective_timeout),
            )
        return self._client

    @property
    def db(self):
        client = self._ensure_client()
        return client[self.settings.mongo_db]

    def health(self, timeout_seconds: Optional[float] = 3.0) -> HealthStatus:
        """Ping MongoDB, retrieve version, and measure ping round-trip latency."""
        start_time = time.perf_counter()
        timeout_ms = int((timeout_seconds or 3.0) * 1000)
        temp_client = None
        try:
            temp_client = MongoClient(
                host=self.settings.mongo_host,
                port=self.settings.mongo_port,
                username=self.settings.mongo_initdb_root_username,
                password=self.settings.mongo_initdb_root_password,
                authSource="admin",
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=min(3000, timeout_ms),
            )
            # Send ping command to admin database
            temp_client.admin.command("ping")
            build_info = temp_client.admin.command("buildInfo")
            version_str = build_info.get("version", "unknown")
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            return HealthStatus(
                is_healthy=True,
                engine=self.engine_name,
                version=f"MongoDB {version_str}",
                latency_ms=elapsed_ms,
                connection_info=self.conn_info,
            )
        except (ServerSelectionTimeoutError, PyMongoError, Exception) as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return HealthStatus(
                is_healthy=False,
                engine=self.engine_name,
                version=None,
                latency_ms=elapsed_ms,
                connection_info=self.conn_info,
                error=f"MongoDB connection error: {str(e)}",
            )
        finally:
            if temp_client is not None:
                temp_client.close()

    def prepare(self) -> None:
        """Warm up client connection pool."""
        client = self._ensure_client()
        client.admin.command("ping")

    def execute(
        self,
        query_id: str,
        params: Dict[str, Any],
        timed: bool = True,
    ) -> QueryResult:
        """Execute Mongo find or aggregate pipeline.

        Timed region strictly measures execution and full cursor consumption into memory.
        """
        from app.domain.query_catalog import MONGO_BUILDERS, normalize_query_output

        db = self.db
        if query_id in MONGO_BUILDERS:
            q_def = MONGO_BUILDERS[query_id](params)
        elif query_id.startswith("live_test") and "collection" in params:
            q_def = {
                "collection": params["collection"],
                "type": params.get("type", params.get("operation", "find")),
                "filter": params.get("filter", {}),
            }
        else:
            raise ValueError(f"Query '{query_id}' not found in MongoDB catalog.")

        collection_name = q_def.get("collection", "orders")
        op_type = q_def.get("type", "find")  # "find" | "aggregate" | "count"
        coll = db[collection_name]

        if op_type == "aggregate":
            pipeline = q_def.get("pipeline", [])
            if timed:
                t_start = time.perf_counter_ns()
                cursor = coll.aggregate(pipeline)
                rows = list(cursor)
                t_end = time.perf_counter_ns()
                execution_time_ms = (t_end - t_start) / 1_000_000.0
            else:
                cursor = coll.aggregate(pipeline)
                rows = list(cursor)
                execution_time_ms = 0.0
        elif op_type == "count":
            filter_doc = q_def.get("filter", {})
            if timed:
                t_start = time.perf_counter_ns()
                count = coll.count_documents(filter_doc)
                t_end = time.perf_counter_ns()
                execution_time_ms = (t_end - t_start) / 1_000_000.0
            else:
                count = coll.count_documents(filter_doc)
                execution_time_ms = 0.0
            rows = [{"order_count": count}]
        else:
            filter_doc = q_def.get("filter", {})
            projection = q_def.get("projection", None)
            sort = q_def.get("sort", None)
            skip = q_def.get("skip", 0)
            limit = q_def.get("limit", 0)

            if timed:
                t_start = time.perf_counter_ns()
                cursor = coll.find(filter_doc, projection)
                if sort:
                    cursor = cursor.sort(sort)
                if skip > 0:
                    cursor = cursor.skip(skip)
                if limit > 0:
                    cursor = cursor.limit(limit)
                rows = list(cursor)
                t_end = time.perf_counter_ns()
                execution_time_ms = (t_end - t_start) / 1_000_000.0
            else:
                cursor = coll.find(filter_doc, projection)
                if sort:
                    cursor = cursor.sort(sort)
                if skip > 0:
                    cursor = cursor.skip(skip)
                if limit > 0:
                    cursor = cursor.limit(limit)
                rows = list(cursor)
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
        """Obtain executionStats explain plan for diagnostic analysis."""
        from app.domain.query_catalog import MONGO_BUILDERS

        db = self.db
        if query_id in MONGO_BUILDERS:
            q_def = MONGO_BUILDERS[query_id](params)
        elif query_id.startswith("live_test") and "collection" in params:
            q_def = {
                "collection": params["collection"],
                "type": params.get("type", params.get("operation", "find")),
                "filter": params.get("filter", {}),
            }
        else:
            raise ValueError(f"Query '{query_id}' not found in MongoDB catalog.")

        collection_name = q_def.get("collection", "orders")
        op_type = q_def.get("type", "find")
        coll = db[collection_name]

        if op_type == "aggregate":
            pipeline = q_def.get("pipeline", [])
            raw_plan = db.command(
                "explain",
                {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}},
                verbosity="executionStats",
            )
        elif op_type == "count":
            pipeline = [{"$match": q_def.get("filter", {})}, {"$group": {"_id": None, "n": {"$sum": 1}}}]
            raw_plan = db.command(
                "explain",
                {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}},
                verbosity="executionStats",
            )
        else:
            filter_doc = q_def.get("filter", {})
            projection = q_def.get("projection", None)
            sort = q_def.get("sort", None)
            skip = q_def.get("skip", 0)
            limit = q_def.get("limit", 0)

            cmd: Dict[str, Any] = {"find": collection_name, "filter": filter_doc}
            if projection:
                cmd["projection"] = projection
            if sort:
                cmd["sort"] = dict(sort) if isinstance(sort, list) else sort
            if skip > 0:
                cmd["skip"] = skip
            if limit > 0:
                cmd["limit"] = limit

            raw_plan = db.command("explain", cmd, verbosity="executionStats")

        # Extract executionStats stage metrics
        stats = raw_plan.get("executionStats", {})
        exec_stage = stats.get("executionStages", {})
        scan_type = exec_stage.get("stage")
        index_used = exec_stage.get("indexName")
        exec_time = stats.get("executionTimeMillis")

        return ExplainResult(
            query_name=query_id,
            engine=self.engine_name,
            raw_plan=raw_plan,
            scan_type=scan_type,
            index_used=index_used,
            execution_time_ms=float(exec_time) if exec_time is not None else None,
        )

    def describe_indexes(self) -> List[IndexInfo]:
        """Inspect all user collections and their active indexes."""
        indexes: List[IndexInfo] = []
        try:
            db = self.db
            for coll_name in db.list_collection_names():
                if coll_name.startswith("system."):
                    continue
                info = db[coll_name].index_information()
                for idx_name, idx_spec in info.items():
                    key_fields = [f"{field}_{direction}" for field, direction in idx_spec.get("key", [])]
                    is_unique = bool(idx_spec.get("unique", False))
                    indexes.append(
                        IndexInfo(
                            index_name=idx_name,
                            entity_name=coll_name,
                            fields=key_fields,
                            is_unique=is_unique,
                        )
                    )
        except Exception:
            pass
        return indexes

    def close(self) -> None:
        """Close MongoClient connections."""
        if self._client is not None:
            self._client.close()
            self._client = None
