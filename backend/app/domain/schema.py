"""Schema management for PostgreSQL and MongoDB.
Applies DDL, constraints, and JSON schema validators for Track A and Track B.
"""

import json
from pathlib import Path
from typing import Any, Dict
import pymongo

from app.adapters.mongodb import MongoAdapter
from app.adapters.postgres import PostgresAdapter

SQL_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "queries" / "postgresql" / "schema.sql"
MONGO_VALIDATORS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "queries" / "mongodb" / "validators.json"

POSTGRES_DDL = """
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE products (
    product_id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_code VARCHAR(20) NOT NULL,
    base_price_minor BIGINT NOT NULL CHECK (base_price_minor >= 0)
);

CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    order_date TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    total_minor BIGINT NOT NULL CHECK (total_minor >= 0)
);

CREATE TABLE order_items (
    order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    product_id BIGINT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price_minor BIGINT NOT NULL CHECK (unit_price_minor >= 0),
    PRIMARY KEY (order_id, line_no)
);
"""


def load_mongo_validators() -> Dict[str, Any]:
    if MONGO_VALIDATORS_PATH.exists():
        with open(MONGO_VALIDATORS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def apply_postgres_schema(adapter: PostgresAdapter) -> None:
    """Execute DDL statements on PostgreSQL."""
    pool = adapter._ensure_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_DDL)


def drop_postgres_schema(adapter: PostgresAdapter) -> None:
    """Drop user tables in PostgreSQL."""
    pool = adapter._ensure_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DROP TABLE IF EXISTS order_items CASCADE;
                DROP TABLE IF EXISTS orders CASCADE;
                DROP TABLE IF EXISTS products CASCADE;
                DROP TABLE IF EXISTS customers CASCADE;
            """)


def apply_mongo_schema(adapter: MongoAdapter) -> None:
    """Create MongoDB collections with validators and basic unique indexes."""
    db = adapter.db
    validators = load_mongo_validators()

    # Track A Collections
    for coll_name in ["customers", "products", "orders", "order_items", "orders_embedded"]:
        validator = validators.get(coll_name, {})
        if coll_name not in db.list_collection_names():
            if validator:
                db.create_collection(coll_name, validator=validator)
            else:
                db.create_collection(coll_name)
        elif validator:
            db.command("collMod", coll_name, validator=validator)

    # Core uniqueness constraint for order_items (order_id, line_no)
    db.order_items.create_index(
        [("order_id", pymongo.ASCENDING), ("line_no", pymongo.ASCENDING)],
        unique=True,
        name="idx_order_items_compound_pk",
    )


def drop_mongo_schema(adapter: MongoAdapter) -> None:
    """Drop user collections in MongoDB."""
    db = adapter.db
    for coll_name in ["customers", "products", "orders", "order_items", "orders_embedded"]:
        if coll_name in db.list_collection_names():
            db[coll_name].drop()
