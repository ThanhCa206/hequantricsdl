"""MongoDB query definitions and pipeline builders for Q1–Q8.
Strictly implements SPEC.md Section 5.
"""

from typing import Any, Dict, List


def build_mongo_q1(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q1: Point lookup by order_id."""
    return {
        "collection": "orders",
        "type": "find",
        "filter": {"_id": params["order_id"]},
        "projection": {
            "_id": 1,
            "customer_id": 1,
            "order_date": 1,
            "status": 1,
            "total_minor": 1,
        },
        "limit": 1,
    }


def build_mongo_q2(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q2: 50 recent orders for a customer."""
    return {
        "collection": "orders",
        "type": "find",
        "filter": {"customer_id": params["customer_id"]},
        "projection": {
            "_id": 1,
            "customer_id": 1,
            "order_date": 1,
            "status": 1,
            "total_minor": 1,
        },
        "sort": [("order_date", -1), ("_id", -1)],
        "limit": 50,
    }


def build_mongo_q3(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q3: Filter orders by status and date range [from_ts, to_ts)."""
    return {
        "collection": "orders",
        "type": "find",
        "filter": {
            "status": params["status"],
            "order_date": {"$gte": params["from_ts"], "$lt": params["to_ts"]},
        },
        "projection": {
            "_id": 1,
            "customer_id": 1,
            "order_date": 1,
            "status": 1,
            "total_minor": 1,
        },
        "sort": [("order_date", -1), ("_id", -1)],
        "limit": 100,
    }


def build_mongo_q4(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q4: Exact count of orders by status and date range."""
    return {
        "collection": "orders",
        "type": "count",
        "filter": {
            "status": params["status"],
            "order_date": {"$gte": params["from_ts"], "$lt": params["to_ts"]},
        },
    }


def build_mongo_q5(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q5: Monthly revenue and order count for 'paid' orders."""
    pipeline = [
        {
            "$match": {
                "status": "paid",
                "order_date": {"$gte": params["from_ts"], "$lt": params["to_ts"]},
            }
        },
        {
            "$group": {
                "_id": {"$substr": ["$order_date", 0, 7]},  # "YYYY-MM"
                "order_count": {"$sum": 1},
                "revenue_minor": {"$sum": "$total_minor"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "month_utc": {"$concat": ["$_id", "-01T00:00:00.000Z"]},
                "order_count": 1,
                "revenue_minor": 1,
            }
        },
        {"$sort": {"month_utc": 1}},
    ]
    return {
        "collection": "orders",
        "type": "aggregate",
        "pipeline": pipeline,
    }


def build_mongo_q6(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q6: Top 10 customers by revenue for 'paid' orders in date range."""
    pipeline = [
        {
            "$match": {
                "status": "paid",
                "order_date": {"$gte": params["from_ts"], "$lt": params["to_ts"]},
            }
        },
        {
            "$group": {
                "_id": "$customer_id",
                "order_count": {"$sum": 1},
                "revenue_minor": {"$sum": "$total_minor"},
            }
        },
        {"$sort": {"revenue_minor": -1, "_id": 1}},
        {"$limit": 10},
        {
            "$lookup": {
                "from": "customers",
                "localField": "_id",
                "foreignField": "_id",
                "as": "customer_info",
            }
        },
        {"$unwind": "$customer_info"},
        {
            "$project": {
                "_id": 0,
                "customer_id": "$_id",
                "name": "$customer_info.name",
                "revenue_minor": 1,
                "order_count": 1,
            }
        },
        {"$sort": {"revenue_minor": -1, "customer_id": 1}},
    ]
    return {
        "collection": "orders",
        "type": "aggregate",
        "pipeline": pipeline,
    }


def build_mongo_q7_offset(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q7_offset: Deep pagination using skip / offset."""
    return {
        "collection": "orders",
        "type": "find",
        "filter": {},
        "projection": {
            "_id": 1,
            "customer_id": 1,
            "order_date": 1,
            "status": 1,
            "total_minor": 1,
        },
        "sort": [("order_date", -1), ("_id", -1)],
        "skip": params.get("offset", 0),
        "limit": 50,
    }


def build_mongo_q7_keyset(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q7_keyset: Keyset pagination using composite anchor (order_date, order_id)."""
    filter_doc: Dict[str, Any] = {}
    last_date = params.get("last_order_date")
    last_id = params.get("last_order_id")

    if last_date is not None and last_id is not None:
        filter_doc = {
            "$or": [
                {"order_date": {"$lt": last_date}},
                {"order_date": last_date, "_id": {"$lt": last_id}},
            ]
        }

    return {
        "collection": "orders",
        "type": "find",
        "filter": filter_doc,
        "projection": {
            "_id": 1,
            "customer_id": 1,
            "order_date": 1,
            "status": 1,
            "total_minor": 1,
        },
        "sort": [("order_date", -1), ("_id", -1)],
        "limit": 50,
    }


def build_mongo_q8_track_a(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q8 Track A: Order details with $lookup join from order_items (Reference model)."""
    pipeline = [
        {"$match": {"_id": params["order_id"]}},
        {
            "$lookup": {
                "from": "order_items",
                "let": {"oid": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$order_id", "$$oid"]}}},
                    {"$sort": {"line_no": 1}},
                    {
                        "$project": {
                            "_id": 0,
                            "line_no": 1,
                            "product_id": 1,
                            "quantity": 1,
                            "unit_price_minor": 1,
                        }
                    },
                ],
                "as": "items",
            }
        },
        {
            "$project": {
                "_id": 0,
                "order_id": "$_id",
                "customer_id": 1,
                "order_date": 1,
                "status": 1,
                "total_minor": 1,
                "items": 1,
            }
        },
    ]
    return {
        "collection": "orders",
        "type": "aggregate",
        "pipeline": pipeline,
    }


def build_mongo_q8_track_b(params: Dict[str, Any]) -> Dict[str, Any]:
    """Q8 Track B: Order details with embedded items array (Embedded model)."""
    return {
        "collection": "orders_embedded",
        "type": "find",
        "filter": {"_id": params["order_id"]},
        "projection": {
            "_id": 1,
            "customer_id": 1,
            "order_date": 1,
            "status": 1,
            "total_minor": 1,
            "items": 1,
        },
        "limit": 1,
    }
