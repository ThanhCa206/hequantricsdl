"""Index Catalog definitions and management for I0 and I1 profiles.
Strictly implements SPEC.md Section 6.1:
- I0: Primary keys & unique constraints only (PKs, Mongo _id, order_items(order_id, line_no) unique).
- I1: Workload secondary indexes for Q2, Q3-Q6, and Q7.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal
import pymongo

from app.adapters.mongodb import MongoAdapter
from app.adapters.postgres import PostgresAdapter

IndexProfile = Literal["I0", "I1"]

# PostgreSQL I1 index statements
POSTGRES_I1_STATEMENTS = [
    (
        "idx_orders_customer_date",
        "orders",
        "CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON orders (customer_id, order_date DESC, order_id DESC);",
    ),
    (
        "idx_orders_status_date",
        "orders",
        "CREATE INDEX IF NOT EXISTS idx_orders_status_date ON orders (status, order_date DESC, order_id DESC);",
    ),
    (
        "idx_orders_date_id",
        "orders",
        "CREATE INDEX IF NOT EXISTS idx_orders_date_id ON orders (order_date DESC, order_id DESC);",
    ),
]

# MongoDB I1 index definitions
MONGO_I1_DEFINITIONS = [
    # orders collection
    (
        "orders",
        "idx_orders_customer_date",
        [("customer_id", pymongo.ASCENDING), ("order_date", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)],
    ),
    (
        "orders",
        "idx_orders_status_date",
        [("status", pymongo.ASCENDING), ("order_date", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)],
    ),
    (
        "orders",
        "idx_orders_date_id",
        [("order_date", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)],
    ),
    # Track B orders_embedded collection
    (
        "orders_embedded",
        "idx_orders_emb_customer_date",
        [("customer_id", pymongo.ASCENDING), ("order_date", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)],
    ),
    (
        "orders_embedded",
        "idx_orders_emb_status_date",
        [("status", pymongo.ASCENDING), ("order_date", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)],
    ),
    (
        "orders_embedded",
        "idx_orders_emb_date_id",
        [("order_date", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)],
    ),
]


def apply_indexes_postgres(adapter: PostgresAdapter, profile: IndexProfile) -> Dict[str, Any]:
    """Apply I0 or I1 indexes to PostgreSQL. Reverting to I0 preserves primary keys."""
    start_time = time.perf_counter()
    pool = adapter._ensure_pool()
    applied: List[str] = []

    with pool.connection() as conn:
        with conn.cursor() as cur:
            if profile == "I0":
                # Drop all secondary workload indexes, preserving PKs
                for idx_name, _, _ in POSTGRES_I1_STATEMENTS:
                    cur.execute(f"DROP INDEX IF EXISTS {idx_name};")
                    applied.append(f"DROP {idx_name}")
            elif profile == "I1":
                # Create workload indexes
                for idx_name, _, stmt in POSTGRES_I1_STATEMENTS:
                    cur.execute(stmt)
                    applied.append(idx_name)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return {
        "engine": "postgresql",
        "profile": profile,
        "applied_indexes": applied,
        "duration_ms": round(elapsed_ms, 2),
    }


def apply_indexes_mongo(adapter: MongoAdapter, profile: IndexProfile) -> Dict[str, Any]:
    """Apply I0 or I1 indexes to MongoDB. Reverting to I0 preserves _id and unique compound key."""
    start_time = time.perf_counter()
    db = adapter.db
    applied: List[str] = []

    if profile == "I0":
        # Drop secondary indexes on orders and orders_embedded
        for coll_name, idx_name, _ in MONGO_I1_DEFINITIONS:
            if coll_name in db.list_collection_names():
                try:
                    db[coll_name].drop_index(idx_name)
                    applied.append(f"DROP {coll_name}.{idx_name}")
                except Exception:
                    pass
    elif profile == "I1":
        # Create workload secondary indexes
        for coll_name, idx_name, keys in MONGO_I1_DEFINITIONS:
            if coll_name in db.list_collection_names():
                db[coll_name].create_index(keys, name=idx_name)
                applied.append(f"{coll_name}.{idx_name}")

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return {
        "engine": "mongodb",
        "profile": profile,
        "applied_indexes": applied,
        "duration_ms": round(elapsed_ms, 2),
    }


def apply_indexes(engine: str, profile: IndexProfile, adapter: Any) -> Dict[str, Any]:
    """Unified index application handler."""
    normalized = engine.lower()
    if "postgres" in normalized:
        return apply_indexes_postgres(adapter, profile)
    elif "mongo" in normalized:
        return apply_indexes_mongo(adapter, profile)
    else:
        raise ValueError(f"Unsupported engine: {engine}")
