"""Independent Python Oracle for Query Correctness Verification.
Strictly implements SPEC.md Section 5.
Does NOT use PostgreSQL or MongoDB; computes 100% pure Python ground-truth results.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional


class PythonOracle:
    """Computes exact ground-truth query results directly on in-memory entity lists."""

    def __init__(
        self,
        customers: List[Dict[str, Any]],
        products: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        order_items: List[Dict[str, Any]],
    ):
        self.customers = customers
        self.products = products
        self.orders = orders
        self.order_items = order_items

        # Build lookups
        self.customers_by_id = {c["customer_id"]: c for c in customers}
        self.products_by_id = {p["product_id"]: p for p in products}

        self.items_by_order: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for it in order_items:
            self.items_by_order[it["order_id"]].append(it)

    def execute_q1(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q1: Lấy một đơn theo order_id."""
        oid = int(params["order_id"])
        for o in self.orders:
            if o["order_id"] == oid:
                return [
                    {
                        "order_id": o["order_id"],
                        "customer_id": o["customer_id"],
                        "order_date": o["order_date"],
                        "status": o["status"],
                        "total_minor": o["total_minor"],
                    }
                ]
        return []

    def execute_q2(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q2: 50 đơn mới nhất của khách hàng."""
        cid = int(params["customer_id"])
        matched = [o for o in self.orders if o["customer_id"] == cid]
        # Sort order_date DESC, order_id DESC
        sorted_orders = sorted(matched, key=lambda x: (x["order_date"], x["order_id"]), reverse=True)
        return [
            {
                "order_id": o["order_id"],
                "customer_id": o["customer_id"],
                "order_date": o["order_date"],
                "status": o["status"],
                "total_minor": o["total_minor"],
            }
            for o in sorted_orders[:50]
        ]

    def execute_q3(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q3: Lọc trạng thái và khoảng ngày [from_ts, to_ts), limit 100."""
        status = params["status"]
        from_ts = params["from_ts"]
        to_ts = params["to_ts"]

        matched = [
            o
            for o in self.orders
            if o["status"] == status and from_ts <= o["order_date"] < to_ts
        ]
        sorted_orders = sorted(matched, key=lambda x: (x["order_date"], x["order_id"]), reverse=True)
        return [
            {
                "order_id": o["order_id"],
                "customer_id": o["customer_id"],
                "order_date": o["order_date"],
                "status": o["status"],
                "total_minor": o["total_minor"],
            }
            for o in sorted_orders[:100]
        ]

    def execute_q4(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q4: Đếm chính xác đơn theo trạng thái và khoảng ngày."""
        status = params["status"]
        from_ts = params["from_ts"]
        to_ts = params["to_ts"]

        count = sum(
            1
            for o in self.orders
            if o["status"] == status and from_ts <= o["order_date"] < to_ts
        )
        return [{"order_count": count}]

    def execute_q5(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q5: Doanh thu và số đơn theo tháng (chỉ đơn 'paid')."""
        from_ts = params["from_ts"]
        to_ts = params["to_ts"]

        monthly: Dict[str, Dict[str, int]] = defaultdict(lambda: {"order_count": 0, "revenue_minor": 0})

        for o in self.orders:
            if o["status"] == "paid" and from_ts <= o["order_date"] < to_ts:
                # "YYYY-MM"
                month_key = o["order_date"][:7]
                monthly[month_key]["order_count"] += 1
                monthly[month_key]["revenue_minor"] += o["total_minor"]

        result = []
        for m_key in sorted(monthly.keys()):
            result.append({
                "month_utc": f"{m_key}-01T00:00:00.000Z",
                "order_count": monthly[m_key]["order_count"],
                "revenue_minor": monthly[m_key]["revenue_minor"],
            })
        return result

    def execute_q6(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q6: Top 10 khách mua nhiều nhất theo doanh thu."""
        from_ts = params["from_ts"]
        to_ts = params["to_ts"]

        cust_stats: Dict[int, Dict[str, int]] = defaultdict(lambda: {"order_count": 0, "revenue_minor": 0})

        for o in self.orders:
            if o["status"] == "paid" and from_ts <= o["order_date"] < to_ts:
                cid = o["customer_id"]
                cust_stats[cid]["order_count"] += 1
                cust_stats[cid]["revenue_minor"] += o["total_minor"]

        # Sort: revenue_minor DESC, customer_id ASC
        sorted_custs = sorted(
            cust_stats.items(),
            key=lambda item: (-item[1]["revenue_minor"], item[0]),
        )[:10]

        result = []
        for cid, stats in sorted_custs:
            cust_name = self.customers_by_id[cid]["name"]
            result.append({
                "customer_id": cid,
                "name": cust_name,
                "revenue_minor": stats["revenue_minor"],
                "order_count": stats["order_count"],
            })
        return result

    def execute_q7_offset(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q7_offset: Phân trang bằng offset."""
        offset = int(params.get("offset", 0))
        sorted_orders = sorted(self.orders, key=lambda x: (x["order_date"], x["order_id"]), reverse=True)
        slice_orders = sorted_orders[offset : offset + 50]
        return [
            {
                "order_id": o["order_id"],
                "customer_id": o["customer_id"],
                "order_date": o["order_date"],
                "status": o["status"],
                "total_minor": o["total_minor"],
            }
            for o in slice_orders
        ]

    def execute_q7_keyset(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q7_keyset: Phân trang bằng keyset anchor."""
        last_date = params.get("last_order_date")
        last_id = params.get("last_order_id")

        if last_date is None or last_id is None:
            filtered = self.orders
        else:
            last_id = int(last_id)
            filtered = [
                o
                for o in self.orders
                if (o["order_date"] < last_date)
                or (o["order_date"] == last_date and o["order_id"] < last_id)
            ]

        sorted_orders = sorted(filtered, key=lambda x: (x["order_date"], x["order_id"]), reverse=True)
        return [
            {
                "order_id": o["order_id"],
                "customer_id": o["customer_id"],
                "order_date": o["order_date"],
                "status": o["status"],
                "total_minor": o["total_minor"],
            }
            for o in sorted_orders[:50]
        ]

    def execute_q8(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Q8: Chi tiết đơn hàng kèm các dòng sản phẩm."""
        oid = int(params["order_id"])
        target_order = None
        for o in self.orders:
            if o["order_id"] == oid:
                target_order = o
                break

        if not target_order:
            return []

        lines = self.items_by_order.get(oid, [])
        sorted_lines = sorted(lines, key=lambda l: l["line_no"])

        items_out = [
            {
                "line_no": l["line_no"],
                "product_id": l["product_id"],
                "quantity": l["quantity"],
                "unit_price_minor": l["unit_price_minor"],
            }
            for l in sorted_lines
        ]

        return [
            {
                "order_id": target_order["order_id"],
                "customer_id": target_order["customer_id"],
                "order_date": target_order["order_date"],
                "status": target_order["status"],
                "total_minor": target_order["total_minor"],
                "items": items_out,
            }
        ]

    def execute(self, query_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute query by ID on Oracle."""
        handlers = {
            "Q1": self.execute_q1,
            "Q2": self.execute_q2,
            "Q3": self.execute_q3,
            "Q4": self.execute_q4,
            "Q5": self.execute_q5,
            "Q6": self.execute_q6,
            "Q7_offset": self.execute_q7_offset,
            "Q7_keyset": self.execute_q7_keyset,
            "Q8": self.execute_q8,
            "Q8_track_a": self.execute_q8,
            "Q8_track_b": self.execute_q8,
        }
        if query_id not in handlers:
            raise ValueError(f"Unknown query_id '{query_id}' for Python Oracle")
        return handlers[query_id](params)
