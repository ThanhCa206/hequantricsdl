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

_SHARED_ADAPTERS: Dict[str, BaseAdapter] = {}


def get_adapter(engine: str, shared: bool = True) -> BaseAdapter:
    """Return an adapter instance for the specified engine name.
    
    If shared=True (default), returns a shared singleton adapter to avoid
    exhausting PostgreSQL/MongoDB connection pools.
    """
    normalized = engine.strip().lower()
    if normalized not in _ADAPTER_REGISTRY:
        raise ValueError(
            f"Unsupported engine '{engine}'. Supported engines: {list(_ADAPTER_REGISTRY.keys())}"
        )
    canonical = "postgresql" if normalized in ("postgresql", "postgres") else "mongodb"
    if shared:
        if canonical not in _SHARED_ADAPTERS:
            _SHARED_ADAPTERS[canonical] = _ADAPTER_REGISTRY[canonical]()
        return _SHARED_ADAPTERS[canonical]
    return _ADAPTER_REGISTRY[canonical]()


def close_all_adapters() -> None:
    """Gracefully close all shared adapter connection pools and sockets."""
    for adapter in list(_SHARED_ADAPTERS.values()):
        try:
            adapter.close()
        except Exception:
            pass
    _SHARED_ADAPTERS.clear()


__all__ = [
    "BaseAdapter",
    "PostgresAdapter",
    "MongoAdapter",
    "HealthStatus",
    "QueryResult",
    "ExplainResult",
    "IndexInfo",
    "get_adapter",
    "close_all_adapters",
]
