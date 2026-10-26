"""Query catalog registry, parameter pool generation, and output normalization.
Strictly implements SPEC.md Section 5.
"""

import copy
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from configs.profiles import DatasetProfile
from queries.mongodb.queries import (
    build_mongo_q1,
    build_mongo_q2,
    build_mongo_q3,
    build_mongo_q4,
    build_mongo_q5,
    build_mongo_q6,
    build_mongo_q7_keyset,
    build_mongo_q7_offset,
    build_mongo_q8_track_a,
    build_mongo_q8_track_b,
)

POSTGRES_QUERIES = {
    "Q1": """
        SELECT order_id, customer_id, order_date, status, total_minor
        FROM orders
        WHERE order_id = %(order_id)s;
    """,
    "Q2": """
        SELECT order_id, customer_id, order_date, status, total_minor
        FROM orders
        WHERE customer_id = %(customer_id)s
        ORDER BY order_date DESC, order_id DESC
        LIMIT 50;
    """,
    "Q3": """
        SELECT order_id, customer_id, order_date, status, total_minor
        FROM orders
        WHERE status = %(status)s
          AND order_date >= %(from_ts)s
          AND order_date < %(to_ts)s
        ORDER BY order_date DESC, order_id DESC
        LIMIT 100;
    """,
    "Q4": """
        SELECT COUNT(*) AS order_count
        FROM orders
        WHERE status = %(status)s
          AND order_date >= %(from_ts)s
          AND order_date < %(to_ts)s;
    """,
    "Q5": """
        SELECT to_char(date_trunc('month', order_date AT TIME ZONE 'UTC'), 'YYYY-MM-01T00:00:00.000Z') AS month_utc,
               COUNT(*) AS order_count,
               COALESCE(SUM(total_minor), 0)::BIGINT AS revenue_minor
        FROM orders
        WHERE status = 'paid'
          AND order_date >= %(from_ts)s
          AND order_date < %(to_ts)s
        GROUP BY date_trunc('month', order_date AT TIME ZONE 'UTC')
        ORDER BY month_utc ASC;
    """,
    "Q6": """
        SELECT c.customer_id, c.name, agg.revenue_minor, agg.order_count
        FROM (
            SELECT customer_id,
                   COUNT(*) AS order_count,
                   SUM(total_minor)::BIGINT AS revenue_minor
            FROM orders
            WHERE status = 'paid'
              AND order_date >= %(from_ts)s
              AND order_date < %(to_ts)s
            GROUP BY customer_id
            ORDER BY revenue_minor DESC, customer_id ASC
            LIMIT 10
        ) agg
        JOIN customers c ON c.customer_id = agg.customer_id
        ORDER BY agg.revenue_minor DESC, c.customer_id ASC;
    """,
    "Q7_offset": """
        SELECT order_id, customer_id, order_date, status, total_minor
        FROM orders
        ORDER BY order_date DESC, order_id DESC
        LIMIT 50 OFFSET %(offset)s;
    """,
    "Q7_keyset": """
        SELECT order_id, customer_id, order_date, status, total_minor
        FROM orders
        WHERE (%(last_order_date)s::TIMESTAMPTZ IS NULL)
           OR (order_date < %(last_order_date)s::TIMESTAMPTZ)
           OR (order_date = %(last_order_date)s::TIMESTAMPTZ AND order_id < %(last_order_id)s)
        ORDER BY order_date DESC, order_id DESC
        LIMIT 50;
    """,
    "Q8_track_a": """
        SELECT o.order_id,
               o.customer_id,
               o.order_date,
               o.status,
               o.total_minor,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'line_no', it.line_no,
                           'product_id', it.product_id,
                           'quantity', it.quantity,
                           'unit_price_minor', it.unit_price_minor
                       ) ORDER BY it.line_no ASC
                   ) FILTER (WHERE it.line_no IS NOT NULL),
                   '[]'::json
               ) AS items
        FROM orders o
        LEFT JOIN order_items it ON o.order_id = it.order_id
        WHERE o.order_id = %(order_id)s
        GROUP BY o.order_id, o.customer_id, o.order_date, o.status, o.total_minor;
    """,
    "Q8_track_b": """
        SELECT o.order_id,
               o.customer_id,
               o.order_date,
               o.status,
               o.total_minor,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'line_no', it.line_no,
                           'product_id', it.product_id,
                           'quantity', it.quantity,
                           'unit_price_minor', it.unit_price_minor
                       ) ORDER BY it.line_no ASC
                   ) FILTER (WHERE it.line_no IS NOT NULL),
                   '[]'::json
               ) AS items
        FROM orders o
        LEFT JOIN order_items it ON o.order_id = it.order_id
        WHERE o.order_id = %(order_id)s
        GROUP BY o.order_id, o.customer_id, o.order_date, o.status, o.total_minor;
    """,
}

MONGO_BUILDERS = {
    "Q1": build_mongo_q1,
    "Q2": build_mongo_q2,
    "Q3": build_mongo_q3,
    "Q4": build_mongo_q4,
    "Q5": build_mongo_q5,
    "Q6": build_mongo_q6,
    "Q7_offset": build_mongo_q7_offset,
    "Q7_keyset": build_mongo_q7_keyset,
    "Q8_track_a": build_mongo_q8_track_a,
    "Q8_track_b": build_mongo_q8_track_b,
}


@dataclass
class QuerySpec:
    query_id: str
    name: str
    description: str
    track: str  # "A" or "B"
    sql: str
    mongo_builder: Callable[[Dict[str, Any]], Dict[str, Any]]


QUERY_SPECS: Dict[str, QuerySpec] = {
    "Q1": QuerySpec(
        query_id="Q1",
        name="Lấy một đơn theo ID",
        description="Point lookup by primary key order_id",
        track="A",
        sql=POSTGRES_QUERIES["Q1"],
        mongo_builder=MONGO_BUILDERS["Q1"],
    ),
    "Q2": QuerySpec(
        query_id="Q2",
        name="50 đơn mới nhất của khách hàng",
        description="Filter by customer_id, sort by order_date desc, order_id desc, limit 50",
        track="A",
        sql=POSTGRES_QUERIES["Q2"],
        mongo_builder=MONGO_BUILDERS["Q2"],
    ),
    "Q3": QuerySpec(
        query_id="Q3",
        name="Lọc đơn hàng theo trạng thái và khoảng ngày",
        description="Filter status and date range [from_ts, to_ts), limit 100",
        track="A",
        sql=POSTGRES_QUERIES["Q3"],
        mongo_builder=MONGO_BUILDERS["Q3"],
    ),
    "Q4": QuerySpec(
        query_id="Q4",
        name="Đếm chính xác đơn hàng theo trạng thái và ngày",
        description="COUNT(*) of orders matching status and date window",
        track="A",
        sql=POSTGRES_QUERIES["Q4"],
        mongo_builder=MONGO_BUILDERS["Q4"],
    ),
    "Q5": QuerySpec(
        query_id="Q5",
        name="Doanh thu và số đơn theo tháng",
        description="Monthly aggregation of paid revenue and order count",
        track="A",
        sql=POSTGRES_QUERIES["Q5"],
        mongo_builder=MONGO_BUILDERS["Q5"],
    ),
    "Q6": QuerySpec(
        query_id="Q6",
        name="Top 10 khách hàng theo doanh thu",
        description="Top 10 customers with highest paid revenue in date window",
        track="A",
        sql=POSTGRES_QUERIES["Q6"],
        mongo_builder=MONGO_BUILDERS["Q6"],
    ),
    "Q7_offset": QuerySpec(
        query_id="Q7_offset",
        name="Phân trang sâu - Offset",
        description="Pagination using LIMIT 50 OFFSET n",
        track="A",
        sql=POSTGRES_QUERIES["Q7_offset"],
        mongo_builder=MONGO_BUILDERS["Q7_offset"],
    ),
    "Q7_keyset": QuerySpec(
        query_id="Q7_keyset",
        name="Phân trang sâu - Keyset",
        description="Keyset pagination using composite anchor (order_date, order_id)",
        track="A",
        sql=POSTGRES_QUERIES["Q7_keyset"],
        mongo_builder=MONGO_BUILDERS["Q7_keyset"],
    ),
    "Q8_track_a": QuerySpec(
        query_id="Q8_track_a",
        name="Chi tiết đơn hàng kèm items (Track A - Tham chiếu)",
        description="Order details with line items via JOIN / $lookup",
        track="A",
        sql=POSTGRES_QUERIES["Q8_track_a"],
        mongo_builder=MONGO_BUILDERS["Q8_track_a"],
    ),
    "Q8_track_b": QuerySpec(
        query_id="Q8_track_b",
        name="Chi tiết đơn hàng kèm items (Track B - Nhúng)",
        description="Order details with line items via embedded document",
        track="B",
        sql=POSTGRES_QUERIES["Q8_track_b"],
        mongo_builder=MONGO_BUILDERS["Q8_track_b"],
    ),
}


def normalize_query_output(query_id: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize output from PostgreSQL or MongoDB into standard canonical JSON format.

    - Renames MongoDB `_id` to `order_id` or `customer_id`
    - Formats timestamps to ISO-8601 UTC milliseconds
    - Converts numbers to integers where applicable
    - Ensures items in Q8 are sorted ascending by line_no
    """
    normalized: List[Dict[str, Any]] = []

    for r in rows:
        item_dict = copy.deepcopy(r)

        # Handle MongoDB _id mapping
        if "_id" in item_dict:
            _id_val = item_dict.pop("_id")
            if "order_id" not in item_dict and query_id in ("Q1", "Q2", "Q3", "Q7_offset", "Q7_keyset", "Q8_track_a", "Q8_track_b"):
                item_dict["order_id"] = _id_val
            elif "customer_id" not in item_dict and query_id == "Q6":
                item_dict["customer_id"] = _id_val

        # Format order_date if it is a datetime object
        if "order_date" in item_dict and isinstance(item_dict["order_date"], datetime):
            dt = item_dict["order_date"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            item_dict["order_date"] = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        # Format month_utc if needed
        if "month_utc" in item_dict and isinstance(item_dict["month_utc"], datetime):
            dt = item_dict["month_utc"]
            item_dict["month_utc"] = dt.strftime("%Y-%m-01T00:00:00.000Z")

        # Cast counts and totals to integer
        for num_field in ("order_count", "total_minor", "revenue_minor", "order_id", "customer_id", "product_id"):
            if num_field in item_dict and item_dict[num_field] is not None:
                try:
                    item_dict[num_field] = int(item_dict[num_field])
                except (ValueError, TypeError):
                    pass

        # Sort and normalize nested items for Q8
        if "items" in item_dict and isinstance(item_dict["items"], list):
            sorted_items = []
            for it in item_dict["items"]:
                it_norm = dict(it)
                it_norm.pop("_id", None)
                for f in ("line_no", "product_id", "quantity", "unit_price_minor"):
                    if f in it_norm and it_norm[f] is not None:
                        try:
                            it_norm[f] = int(it_norm[f])
                        except (ValueError, TypeError):
                            pass
                sorted_items.append(it_norm)
            item_dict["items"] = sorted(sorted_items, key=lambda x: x["line_no"])

        normalized.append(item_dict)

    return normalized


def generate_parameter_pool(
    query_id: str,
    profile: DatasetProfile,
    seed: int = 42,
    count: int = 200,
) -> List[Dict[str, Any]]:
    """Generate deterministic parameter pool (>= 200 sets) for benchmark runs."""
    rng = random.Random(seed + hash(query_id) % 10000)
    pool: List[Dict[str, Any]] = []

    num_orders = profile.num_orders
    num_cust = profile.num_customers

    date_base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    max_days = 3 * 365  # 3 years

    for i in range(count):
        if query_id in ("Q1", "Q8", "Q8_track_a", "Q8_track_b"):
            # 95% valid ID, 5% non-existent ID
            if rng.random() < 0.95 or num_orders <= 1:
                oid = rng.randint(1, num_orders)
            else:
                oid = num_orders + rng.randint(100, 1000)
            pool.append({"order_id": oid})

        elif query_id == "Q2":
            cid = rng.randint(1, num_cust)
            pool.append({"customer_id": cid})

        elif query_id in ("Q3", "Q4"):
            status = rng.choice(["pending", "paid", "shipped", "cancelled"])
            # Window size: 1, 30, or 365 days
            window_days = rng.choice([1, 30, 365])
            start_offset = rng.randint(0, max_days - window_days - 1)
            from_dt = date_base + timedelta(days=start_offset)
            to_dt = from_dt + timedelta(days=window_days)
            from_ts = from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            to_ts = to_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            pool.append({"status": status, "from_ts": from_ts, "to_ts": to_ts, "window_days": window_days})

        elif query_id in ("Q5", "Q6"):
            # Date window between 90 and 365 days
            window_days = rng.choice([90, 180, 365])
            start_offset = rng.randint(0, max_days - window_days - 1)
            from_dt = date_base + timedelta(days=start_offset)
            to_dt = from_dt + timedelta(days=window_days)
            from_ts = from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            to_ts = to_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            pool.append({"from_ts": from_ts, "to_ts": to_ts, "window_days": window_days})

        elif query_id == "Q7_offset":
            # Offsets: 0, 100, and deep offsets up to N-50
            max_offset = max(0, num_orders - 50)
            offsets_choices = [0, min(100, max_offset), min(1000, max_offset), min(10000, max_offset)]
            offset = rng.choice(offsets_choices)
            pool.append({"offset": offset})

        elif query_id == "Q7_keyset":
            # Keyset pagination anchor
            if i == 0 or rng.random() < 0.20:
                pool.append({"last_order_date": None, "last_order_id": None})
            else:
                rand_day = rng.randint(10, max_days - 10)
                anchor_dt = date_base + timedelta(days=rand_day, seconds=rng.randint(0, 86399))
                anchor_ts = anchor_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                anchor_id = rng.randint(1, num_orders)
                pool.append({"last_order_date": anchor_ts, "last_order_id": anchor_id})

    return pool
