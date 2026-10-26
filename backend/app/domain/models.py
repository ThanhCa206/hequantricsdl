"""Domain models and data definitions for BenchLab.
Strictly conforms to SPEC.md Section 4:
- 64-bit integer IDs (serialized as strings in JSON API to preserve 53-bit precision)
- Minor currency units (int64)
- UTC millisecond ISO-8601 timestamps
- Core fields NOT NULL
"""

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

OrderStatus = Literal["pending", "paid", "shipped", "cancelled"]

CITY_CODES = [
    "HAN",  # Hanoi
    "SGN",  # Ho Chi Minh City
    "DAD",  # Da Nang
    "CAN",  # Can Tho
    "HPH",  # Hai Phong
    "BDG",  # Binh Duong
    "DNI",  # Dong Nai
    "VTU",  # Vung Tau
    "HUE",  # Hue
    "QNH",  # Quang Ninh
]

CATEGORY_CODES = [f"CAT{i:02d}" for i in range(1, 21)]  # CAT01 to CAT20


def format_utc_iso(dt: datetime) -> str:
    """Format datetime object into canonical UTC ISO-8601 with milliseconds: YYYY-MM-DDTHH:mm:ss.sssZ."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class Customer:
    customer_id: int
    name: str
    city_code: str
    created_at: str  # ISO-8601 UTC ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "city_code": self.city_code,
            "created_at": self.created_at,
        }

    def to_api_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["customer_id"] = str(self.customer_id)
        return d


@dataclass
class Product:
    product_id: int
    name: str
    category_code: str
    base_price_minor: int  # Price in VND (1 unit = 1 VND)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category_code": self.category_code,
            "base_price_minor": self.base_price_minor,
        }

    def to_api_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["product_id"] = str(self.product_id)
        return d


@dataclass
class OrderItem:
    order_id: int
    line_no: int
    product_id: int
    quantity: int
    unit_price_minor: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "line_no": self.line_no,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price_minor": self.unit_price_minor,
        }

    def to_api_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["order_id"] = str(self.order_id)
        d["product_id"] = str(self.product_id)
        return d

    def to_mongo_doc(self) -> Dict[str, Any]:
        """MongoDB Reference representation for order_items collection."""
        return {
            "_id": f"{self.order_id}:{self.line_no}",
            "order_id": self.order_id,
            "line_no": self.line_no,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price_minor": self.unit_price_minor,
        }


@dataclass
class Order:
    order_id: int
    customer_id: int
    order_date: str  # ISO-8601 UTC ms
    status: OrderStatus
    total_minor: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "order_date": self.order_date,
            "status": self.status,
            "total_minor": self.total_minor,
        }

    def to_api_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["order_id"] = str(self.order_id)
        d["customer_id"] = str(self.customer_id)
        return d

    def to_mongo_doc(self) -> Dict[str, Any]:
        """MongoDB Reference representation for orders collection."""
        return {
            "_id": self.order_id,
            "customer_id": self.customer_id,
            "order_date": self.order_date,
            "status": self.status,
            "total_minor": self.total_minor,
        }


@dataclass
class OrderEmbedded:
    """Track B representation: Order with embedded items list."""
    order_id: int
    customer_id: int
    order_date: str
    status: OrderStatus
    total_minor: int
    items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "order_date": self.order_date,
            "status": self.status,
            "total_minor": self.total_minor,
            "items": copy.deepcopy(self.items),
        }

    def to_mongo_doc(self) -> Dict[str, Any]:
        return {
            "_id": self.order_id,
            "customer_id": self.customer_id,
            "order_date": self.order_date,
            "status": self.status,
            "total_minor": self.total_minor,
            "items": self.items,
        }

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "order_id": str(self.order_id),
            "customer_id": str(self.customer_id),
            "order_date": self.order_date,
            "status": self.status,
            "total_minor": self.total_minor,
            "items": [
                {
                    "line_no": it["line_no"],
                    "product_id": str(it["product_id"]),
                    "quantity": it["quantity"],
                    "unit_price_minor": it["unit_price_minor"],
                }
                for it in self.items
            ],
        }
