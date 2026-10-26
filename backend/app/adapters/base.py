"""Abstract Base Adapter for Database Interactions.
Defines core contracts: health, prepare, execute, explain, describe_indexes, close.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HealthStatus:
    """Represents database connectivity and health assessment."""
    is_healthy: bool
    engine: str
    version: Optional[str] = None
    latency_ms: Optional[float] = None
    connection_info: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_healthy": self.is_healthy,
            "engine": self.engine,
            "version": self.version,
            "latency_ms": round(self.latency_ms, 3) if self.latency_ms is not None else None,
            "connection_info": self.connection_info,
            "error": self.error,
        }


@dataclass
class QueryResult:
    """Represents output of an executed query with timed metric."""
    query_name: str
    engine: str
    row_count: int
    data: List[Dict[str, Any]]
    execution_time_ms: float
    status: str = "success"  # "success" | "error" | "timeout"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_name": self.query_name,
            "engine": self.engine,
            "row_count": self.row_count,
            "data": self.data,
            "execution_time_ms": round(self.execution_time_ms, 4),
            "status": self.status,
            "error": self.error,
        }


@dataclass
class ExplainResult:
    """Diagnostic execution plan representation."""
    query_name: str
    engine: str
    raw_plan: Dict[str, Any]
    scan_type: Optional[str] = None
    index_used: Optional[str] = None
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_name": self.query_name,
            "engine": self.engine,
            "raw_plan": self.raw_plan,
            "scan_type": self.scan_type,
            "index_used": self.index_used,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class IndexInfo:
    """Information about an active database index."""
    index_name: str
    entity_name: str  # Table name or Collection name
    fields: List[str]
    is_unique: bool = False
    size_bytes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index_name": self.index_name,
            "entity_name": self.entity_name,
            "fields": self.fields,
            "is_unique": self.is_unique,
            "size_bytes": self.size_bytes,
        }


class BaseAdapter(ABC):
    """Abstract Base Class for all database adapters (PostgreSQL and MongoDB)."""

    def __init__(self, engine_name: str):
        self.engine_name = engine_name

    @abstractmethod
    def health(self, timeout_seconds: Optional[float] = None) -> HealthStatus:
        """Check database ping, version, and connectivity status."""
        pass

    @abstractmethod
    def prepare(self) -> None:
        """Initialize and warm up connection pool."""
        pass

    @abstractmethod
    def execute(
        self,
        query_id: str,
        params: Dict[str, Any],
        timed: bool = True,
    ) -> QueryResult:
        """Execute a predefined query with parameter set and consume cursor.

        Timed region strictly measures database execution and client cursor consumption.
        """
        pass

    @abstractmethod
    def explain(
        self,
        query_id: str,
        params: Dict[str, Any],
    ) -> ExplainResult:
        """Obtain execution plan for diagnostic inspection (outside measurement window)."""
        pass

    @abstractmethod
    def describe_indexes(self) -> List[IndexInfo]:
        """Inspect and describe existing indexes across relevant collections or tables."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close active connection pools and release resources."""
        pass
