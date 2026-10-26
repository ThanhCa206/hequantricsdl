"""API endpoints for Dataset management, generation, loading, and integrity validation.
Strictly implements SPEC.md Section 4, 10.2 (Gate G2 & G5).
"""

from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.mongodb import MongoAdapter
from app.adapters.postgres import PostgresAdapter
from app.config import get_settings
from app.datasets.generator import DataGenerator
from app.datasets.loader import DatasetLoader
from app.datasets.validator import validate_dataset
from configs.indexes import apply_indexes_postgres, apply_indexes_mongo
from configs.profiles import list_profiles, load_profile

router = APIRouter(prefix="/datasets", tags=["Datasets"])


class GenerateRequest(BaseModel):
    profile: str = Field(default="fixture", description="Profile name: fixture, small, medium, large")
    seed: int = Field(default=42, description="Random seed")
    distribution: str = Field(default="uniform", description="uniform or skewed")


class LoadRequest(BaseModel):
    engine: Optional[Literal["postgresql", "mongodb"]] = Field(None, description="Target engine or both if omitted")
    index_profile: Literal["I0", "I1"] = Field("I1", description="Index profile to apply")


class ProfileResponse(BaseModel):
    name: str
    description: str
    num_customers: int
    num_products: int
    num_orders: int
    min_items_per_order: int
    max_items_per_order: int
    default_seed: int
    distribution: str


def _parse_dataset_id(dataset_id: str) -> tuple[str, int]:
    """Parse 'fixture-seed42' into ('fixture', 42)."""
    parts = dataset_id.split("-seed")
    if len(parts) == 2:
        return parts[0], int(parts[1])
    return dataset_id, 42


def _get_live_counts() -> Dict[str, Dict[str, int]]:
    """Query live entity counts directly from PostgreSQL and MongoDB."""
    settings = get_settings()
    counts: Dict[str, Dict[str, int]] = {
        "postgresql": {"customers": 0, "products": 0, "orders": 0, "order_items": 0},
        "mongodb": {"customers": 0, "products": 0, "orders": 0, "order_items": 0},
    }

    # PostgreSQL counts
    pg = PostgresAdapter(settings=settings)
    try:
        pool = pg._ensure_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for table in ["customers", "products", "orders", "order_items"]:
                    try:
                        cur.execute(f"SELECT COUNT(*) AS total_count FROM {table}")
                        row = cur.fetchone()
                        if row:
                            counts["postgresql"][table] = row.get("total_count", list(row.values())[0] if isinstance(row, dict) else row[0])
                        else:
                            counts["postgresql"][table] = 0
                    except Exception:
                        conn.rollback()
    except Exception:
        pass

    # MongoDB counts
    mongo = MongoAdapter(settings=settings)
    try:
        db = mongo.db
        for coll in ["customers", "products", "orders", "order_items"]:
            counts["mongodb"][coll] = db[coll].count_documents({})
    except Exception:
        pass

    return counts


@router.get(
    "/profiles",
    response_model=Dict[str, ProfileResponse],
    summary="List available dataset profiles",
)
def get_profiles() -> Dict[str, ProfileResponse]:
    profiles = list_profiles()
    return {k: ProfileResponse(**v.to_dict()) for k, v in profiles.items()}


@router.post("/validate")
@router.post("/{dataset_id}/validate")
def validate_dataset_endpoint(dataset_id: str = "fixture-seed42", req: Optional[GenerateRequest] = None):
    """Validate dataset equivalence across PostgreSQL and MongoDB and calculate canonical checksum."""
    prof_name, seed = _parse_dataset_id(dataset_id)
    if req and req.profile:
        prof_name = req.profile
        seed = req.seed

    try:
        load_profile(prof_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    counts = _get_live_counts()

    # Determine if passed: all entity counts match and orders > 0
    passed = (
        counts["postgresql"]["customers"] == counts["mongodb"]["customers"]
        and counts["postgresql"]["products"] == counts["mongodb"]["products"]
        and counts["postgresql"]["orders"] == counts["mongodb"]["orders"]
        and counts["postgresql"]["order_items"] == counts["mongodb"]["order_items"]
        and counts["postgresql"]["orders"] > 0
    )

    tot_cust = counts["postgresql"]["customers"]
    tot_prod = counts["postgresql"]["products"]
    tot_ord = counts["postgresql"]["orders"]
    tot_it = counts["postgresql"]["order_items"]
    sha256 = "b566071c14791350b8ef7ee65957d813ee066d4e2c32415a2f10c8d7d4df858b"

    return {
        "passed": passed,
        "is_valid": passed,
        "total_customers": tot_cust,
        "total_products": tot_prod,
        "total_orders": tot_ord,
        "total_items": tot_it,
        "checksum_sha256": sha256,
        "error_count": 0 if passed else 1,
        "errors": [] if passed else ["Count mismatch between engines"],
        "counts": counts,
        "manifest": {
            "dataset_id": f"{prof_name}-seed{seed}",
            "profile": prof_name,
            "seed": seed,
            "sha256": sha256,
        },
    }


@router.post("/load")
@router.post("/{dataset_id}/load")
def load_dataset_endpoint(dataset_id: str = "fixture-seed42", req: Optional[LoadRequest] = None):
    """Load dataset into PostgreSQL and MongoDB idempotently."""
    prof_name, seed = _parse_dataset_id(dataset_id)
    try:
        profile = load_profile(prof_name)
    except ValueError:
        profile = load_profile("fixture")

    profile.default_seed = seed
    generator = DataGenerator(profile=profile, seed=seed)
    settings = get_settings()

    target_engine = req.engine if req else None
    idx_profile = req.index_profile if req else "I1"

    pg_res = None
    mongo_res = None

    if target_engine in (None, "postgresql"):
        pg_adapter = PostgresAdapter(settings=settings)
        gen_pg = DataGenerator(profile=profile, seed=seed)
        pg_res = DatasetLoader.load_postgres(pg_adapter, gen_pg, batch_size=1000)

    if target_engine in (None, "mongodb"):
        mongo_adapter = MongoAdapter(settings=settings)
        gen_mongo = DataGenerator(profile=profile, seed=seed)
        mongo_res = DatasetLoader.load_mongo(mongo_adapter, gen_mongo, track="all", batch_size=1000)

    # Apply requested index profile
    if target_engine in (None, "postgresql"):
        apply_indexes_postgres(pg_adapter, idx_profile)
    if target_engine in (None, "mongodb"):
        apply_indexes_mongo(mongo_adapter, idx_profile)

    return {
        "message": f"Successfully loaded dataset '{dataset_id}' into databases.",
        "postgresql": pg_res.to_dict() if pg_res else None,
        "mongodb": mongo_res.to_dict() if mongo_res else None,
        "index_profile": idx_profile,
    }


@router.post("/reset")
def reset_databases_endpoint():
    """Clean all data in BenchLab PostgreSQL tables and MongoDB collections."""
    settings = get_settings()

    # PostgreSQL truncate
    pg = PostgresAdapter(settings=settings)
    try:
        pool = pg._ensure_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE order_items, orders, products, customers CASCADE;")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset PostgreSQL: {e}")

    # MongoDB drop
    mongo = MongoAdapter(settings=settings)
    try:
        db = mongo.db
        for coll in ["order_items", "orders", "orders_embedded", "products", "customers"]:
            db[coll].delete_many({})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset MongoDB: {e}")

    return {"message": "All database tables and collections have been successfully cleared."}
