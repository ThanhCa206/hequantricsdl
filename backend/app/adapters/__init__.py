"""Adapters package exporting PostgresAdapter, MongoAdapter, and factory function."""

from typing import Dict, Type
from app.adapters.base import (
    BaseAdapter,
    ExplainResult,
    HealthStatus,
    IndexInfo,
    QueryResult,
)
from app.adapters.mongodb import MongoAdapter
from app.adapters.postgres import PostgresAdapter

_ADAPTER_REGISTRY: Dict[str, Type[BaseAdapter]] = {
    "postgresql": PostgresAdapter,
    "postgres": PostgresAdapter,
    "mongodb": MongoAdapter,
    "mongo": MongoAdapter,
}


def get_adapter(engine: str) -> BaseAdapter:
    """Return an adapter instance for the specified engine name."""
    normalized = engine.strip().lower()
    if normalized not in _ADAPTER_REGISTRY:
        raise ValueError(
            f"Unsupported engine '{engine}'. Supported engines: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return _ADAPTER_REGISTRY[normalized]()


__all__ = [
    "BaseAdapter",
    "PostgresAdapter",
    "MongoAdapter",
    "HealthStatus",
    "QueryResult",
    "ExplainResult",
    "IndexInfo",
    "get_adapter",
]
