"""API Router for Query Catalog, Execution, Explain, and Parameter Pools.
Strictly implements SPEC.md Section 5 and Section 9 (Gate G3).
"""

from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters import get_adapter
from app.domain.query_catalog import (
    QUERY_SPECS,
    generate_parameter_pool,
)
from configs.profiles import load_profile

router = APIRouter(prefix="/queries", tags=["Queries"])


class QueryInfo(BaseModel):
    query_id: str
    name: str
    description: str
    track: str
    sql: str


class QueryExecuteRequest(BaseModel):
    engine: Literal["postgresql", "mongodb", "both"] = Field("both", description="Target database engine")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    timed: bool = Field(True, description="Whether to strictly time the query execution")


class SingleEngineQueryResult(BaseModel):
    engine: str
    query_id: str
    row_count: int
    execution_time_ms: float
    data: List[Dict[str, Any]]
    status: str
    error: Optional[str] = None


class QueryExecuteResponse(BaseModel):
    query_id: str
    results: Dict[str, SingleEngineQueryResult]
    is_equivalent: Optional[bool] = None


class QueryExplainRequest(BaseModel):
    engine: Literal["postgresql", "mongodb", "both"] = Field("both", description="Target database engine")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")


class QueryExplainResponse(BaseModel):
    query_id: str
    engine: str
    raw_plan: Dict[str, Any]
    scan_type: Optional[str] = None
    index_used: Optional[str] = None
    execution_time_ms: Optional[float] = None


def _resolve_query_id(query_id: str, variant: Optional[str] = None) -> str:
    """Normalize Q7 and Q8 aliases to explicit variant keys in catalog."""
    if query_id in QUERY_SPECS:
        return query_id
    if query_id == "Q7":
        if variant in ("keyset", "Q7_keyset"):
            return "Q7_keyset"
        return "Q7_offset"
    if query_id == "Q8":
        if variant in ("track_b", "Q8_track_b"):
            return "Q8_track_b"
        return "Q8_track_a"
    return query_id


@router.get("", response_model=List[QueryInfo])
def list_queries():
    """List all available queries in standard catalog (Q1-Q8)."""
    return [
        QueryInfo(
            query_id=spec.query_id,
            name=spec.name,
            description=spec.description,
            track=spec.track,
            sql=spec.sql.strip(),
        )
        for spec in QUERY_SPECS.values()
    ]


@router.get("/{query_id}", response_model=QueryInfo)
def get_query(query_id: str, variant: Optional[str] = None):
    """Retrieve specific query details from catalog."""
    resolved_id = _resolve_query_id(query_id, variant)
    if resolved_id not in QUERY_SPECS:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found in catalog")
    spec = QUERY_SPECS[resolved_id]
    return QueryInfo(
        query_id=spec.query_id,
        name=spec.name,
        description=spec.description,
        track=spec.track,
        sql=spec.sql.strip(),
    )


@router.get("/{query_id}/params")
def get_sample_params(
    query_id: str,
    variant: Optional[str] = None,
    profile: str = Query("fixture", description="Dataset profile (fixture, small, medium, large)"),
    seed: int = Query(42, description="Random seed"),
    count: int = Query(10, ge=1, le=500, description="Number of parameter sets to generate"),
):
    """Generate deterministic parameter pool for a query."""
    resolved_id = _resolve_query_id(query_id, variant)
    if resolved_id not in QUERY_SPECS:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found in catalog")
    prof = load_profile(profile)
    pool = generate_parameter_pool(query_id=resolved_id, profile=prof, seed=seed, count=count)
    return {"query_id": resolved_id, "profile": profile, "seed": seed, "count": len(pool), "parameters": pool}


@router.post("/{query_id}/execute", response_model=QueryExecuteResponse)
def execute_query(query_id: str, request: QueryExecuteRequest):
    """Execute query on PostgreSQL, MongoDB, or both and compare results."""
    variant = request.params.get("variant")
    resolved_id = _resolve_query_id(query_id, variant)
    if resolved_id not in QUERY_SPECS:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found in catalog")

    results: Dict[str, SingleEngineQueryResult] = {}
    engines_to_run = ["postgresql", "mongodb"] if request.engine == "both" else [request.engine]

    for eng in engines_to_run:
        adapter = get_adapter(eng)
        try:
            res = adapter.execute(query_id=resolved_id, params=request.params, timed=request.timed)
            results[eng] = SingleEngineQueryResult(
                engine=eng,
                query_id=resolved_id,
                row_count=res.row_count,
                execution_time_ms=res.execution_time_ms,
                data=res.data,
                status=res.status,
                error=res.error,
            )
        except Exception as e:
            results[eng] = SingleEngineQueryResult(
                engine=eng,
                query_id=resolved_id,
                row_count=0,
                execution_time_ms=0.0,
                data=[],
                status="error",
                error=str(e),
            )

    is_equiv: Optional[bool] = None
    if "postgresql" in results and "mongodb" in results:
        pg_res = results["postgresql"]
        mg_res = results["mongodb"]
        if pg_res.status == "success" and mg_res.status == "success":
            is_equiv = pg_res.data == mg_res.data

    return QueryExecuteResponse(
        query_id=resolved_id,
        results=results,
        is_equivalent=is_equiv,
    )


@router.post("/{query_id}/explain")
def explain_query(query_id: str, request: QueryExplainRequest):
    """Obtain execution plan for query on target database engine (or both)."""
    variant = request.params.get("variant")
    resolved_id = _resolve_query_id(query_id, variant)
    if resolved_id not in QUERY_SPECS:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found in catalog")

    engines_to_run = ["postgresql", "mongodb"] if request.engine == "both" else [request.engine]
    plans: Dict[str, Any] = {}

    for eng in engines_to_run:
        adapter = get_adapter(eng)
        try:
            plan = adapter.explain(query_id=resolved_id, params=request.params)
            plans[eng] = {
                "query_id": resolved_id,
                "engine": eng,
                "raw_plan": plan.raw_plan if isinstance(plan.raw_plan, dict) else {"plan": plan.raw_plan},
                "scan_type": plan.scan_type,
                "index_used": plan.index_used,
                "execution_time_ms": plan.execution_time_ms,
            }
        except Exception as e:
            plans[eng] = {"error": str(e), "engine": eng}

    if request.engine in ("postgresql", "mongodb"):
        return plans.get(request.engine, {})
    return plans
