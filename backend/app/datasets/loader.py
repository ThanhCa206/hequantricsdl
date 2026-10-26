"""Idempotent batch loader for PostgreSQL and MongoDB.
Strictly implements SPEC.md Section 4.4 & 4.5 (DATA-06):
- Idempotent upserts (ON CONFLICT DO UPDATE in PostgreSQL, ReplaceOne(..., upsert=True) in MongoDB)
- Batched streaming import without memory saturation
- Supports Track A (Reference) and Track B (Embedded)
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional
from pymongo import ReplaceOne

from app.adapters.mongodb import MongoAdapter
from app.adapters.postgres import PostgresAdapter
from app.datasets.generator import DataGenerator


@dataclass
class LoadResult:
    engine: str
    track: str
    num_customers: int
    num_products: int
    num_orders: int
    num_items: int
    num_embedded_orders: int
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "track": self.track,
            "num_customers": self.num_customers,
            "num_products": self.num_products,
            "num_orders": self.num_orders,
            "num_items": self.num_items,
            "num_embedded_orders": self.num_embedded_orders,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class DatasetLoader:
    """Manages loading data into target databases with guaranteed idempotency."""

    @staticmethod
    def load_postgres(
        adapter: PostgresAdapter,
        generator: DataGenerator,
        batch_size: int = 1000,
        truncate_first: bool = False,
    ) -> LoadResult:
        """Load dataset into PostgreSQL using batched idempotent upsert statements."""
        t_start = time.perf_counter()
        pool = adapter._ensure_pool()

        total_cust = 0
        total_prod = 0
        total_ord = 0
        total_it = 0

        with pool.connection() as conn:
            with conn.cursor() as cur:
                if truncate_first:
                    cur.execute("TRUNCATE TABLE order_items, orders, products, customers RESTART IDENTITY CASCADE;")
                # 1. Customers
                for cust_batch in generator.stream_customers(batch_size=batch_size):
                    data = [
                        (c.customer_id, c.name, c.city_code, c.created_at)
                        for c in cust_batch
                    ]
                    cur.executemany(
                        """
                        INSERT INTO customers (customer_id, name, city_code, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (customer_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            city_code = EXCLUDED.city_code,
                            created_at = EXCLUDED.created_at;
                        """,
                        data,
                    )
                    total_cust += len(cust_batch)

                # 2. Products
                for prod_batch in generator.stream_products(batch_size=batch_size):
                    data = [
                        (p.product_id, p.name, p.category_code, p.base_price_minor)
                        for p in prod_batch
                    ]
                    cur.executemany(
                        """
                        INSERT INTO products (product_id, name, category_code, base_price_minor)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (product_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            category_code = EXCLUDED.category_code,
                            base_price_minor = EXCLUDED.base_price_minor;
                        """,
                        data,
                    )
                    total_prod += len(prod_batch)

                # 3. Orders and Order Items
                for ord_batch, it_batch, _ in generator.stream_orders(batch_size=batch_size):
                    ord_data = [
                        (o.order_id, o.customer_id, o.order_date, o.status, o.total_minor)
                        for o in ord_batch
                    ]
                    cur.executemany(
                        """
                        INSERT INTO orders (order_id, customer_id, order_date, status, total_minor)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (order_id) DO UPDATE SET
                            customer_id = EXCLUDED.customer_id,
                            order_date = EXCLUDED.order_date,
                            status = EXCLUDED.status,
                            total_minor = EXCLUDED.total_minor;
                        """,
                        ord_data,
                    )
                    total_ord += len(ord_batch)

                    it_data = [
                        (it.order_id, it.line_no, it.product_id, it.quantity, it.unit_price_minor)
                        for it in it_batch
                    ]
                    cur.executemany(
                        """
                        INSERT INTO order_items (order_id, line_no, product_id, quantity, unit_price_minor)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (order_id, line_no) DO UPDATE SET
                            product_id = EXCLUDED.product_id,
                            quantity = EXCLUDED.quantity,
                            unit_price_minor = EXCLUDED.unit_price_minor;
                        """,
                        it_data,
                    )
                    total_it += len(it_batch)

        elapsed = time.perf_counter() - t_start
        return LoadResult(
            engine="postgresql",
            track="A",
            num_customers=total_cust,
            num_products=total_prod,
            num_orders=total_ord,
            num_items=total_it,
            num_embedded_orders=0,
            duration_seconds=elapsed,
        )

    @staticmethod
    def load_mongo(
        adapter: MongoAdapter,
        generator: DataGenerator,
        track: Literal["all", "A", "B"] = "all",
        batch_size: int = 1000,
        truncate_first: bool = False,
    ) -> LoadResult:
        """Load dataset into MongoDB using idempotent ReplaceOne bulk operations."""
        t_start = time.perf_counter()
        db = adapter.db

        if truncate_first:
            for coll in ["customers", "products", "orders", "order_items", "orders_embedded"]:
                try:
                    db[coll].delete_many({})
                except Exception:
                    pass

        total_cust = 0
        total_prod = 0
        total_ord = 0
        total_it = 0
        total_emb = 0

        # Load Customers
        for cust_batch in generator.stream_customers(batch_size=batch_size):
            ops = [
                ReplaceOne(
                    {"_id": c.customer_id},
                    {
                        "_id": c.customer_id,
                        "name": c.name,
                        "city_code": c.city_code,
                        "created_at": c.created_at,
                    },
                    upsert=True,
                )
                for c in cust_batch
            ]
            if ops:
                db.customers.bulk_write(ops, ordered=False)
            total_cust += len(cust_batch)

        # Load Products
        for prod_batch in generator.stream_products(batch_size=batch_size):
            ops = [
                ReplaceOne(
                    {"_id": p.product_id},
                    {
                        "_id": p.product_id,
                        "name": p.name,
                        "category_code": p.category_code,
                        "base_price_minor": p.base_price_minor,
                    },
                    upsert=True,
                )
                for p in prod_batch
            ]
            if ops:
                db.products.bulk_write(ops, ordered=False)
            total_prod += len(prod_batch)

        # Load Orders and Items
        for ord_batch, it_batch, emb_batch in generator.stream_orders(batch_size=batch_size):
            # Track A
            if track in ("all", "A"):
                ord_ops = [
                    ReplaceOne(
                        {"_id": o.order_id},
                        o.to_mongo_doc(),
                        upsert=True,
                    )
                    for o in ord_batch
                ]
                if ord_ops:
                    db.orders.bulk_write(ord_ops, ordered=False)
                total_ord += len(ord_batch)

                it_ops = [
                    ReplaceOne(
                        {"_id": f"{it.order_id}:{it.line_no}"},
                        it.to_mongo_doc(),
                        upsert=True,
                    )
                    for it in it_batch
                ]
                if it_ops:
                    db.order_items.bulk_write(it_ops, ordered=False)
                total_it += len(it_batch)

            # Track B
            if track in ("all", "B"):
                emb_ops = [
                    ReplaceOne(
                        {"_id": emb.order_id},
                        emb.to_mongo_doc(),
                        upsert=True,
                    )
                    for emb in emb_batch
                ]
                if emb_ops:
                    db.orders_embedded.bulk_write(emb_ops, ordered=False)
                total_emb += len(emb_batch)

        elapsed = time.perf_counter() - t_start
        return LoadResult(
            engine="mongodb",
            track=track,
            num_customers=total_cust,
            num_products=total_prod,
            num_orders=total_ord,
            num_items=total_it,
            num_embedded_orders=total_emb,
            duration_seconds=elapsed,
        )
