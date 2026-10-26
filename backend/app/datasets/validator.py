"""Dataset integrity checker and canonical checksum calculator.
Implements SPEC.md Section 4.6 (DATA-01 to DATA-06):
- Canonical JSON serialization and SHA-256 hashing
- Referential integrity (Foreign Keys) validation
- Business calculation validation: order.total_minor == SUM(quantity * unit_price_minor)
- Duplicate key and negative value rejection
- Flattening Track B embedded orders to verify exact 100% equivalence with Track A
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class IntegrityReport:
    is_valid: bool
    total_customers: int
    total_products: int
    total_orders: int
    total_items: int
    total_revenue_minor: int
    checksum_sha256: str
    entity_checksums: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_customers": self.total_customers,
            "total_products": self.total_products,
            "total_orders": self.total_orders,
            "total_items": self.total_items,
            "total_revenue_minor": self.total_revenue_minor,
            "checksum_sha256": self.checksum_sha256,
            "entity_checksums": self.entity_checksums,
            "error_count": len(self.errors),
            "errors": self.errors[:50],  # Return up to 50 errors in summary
        }


def canonical_json_dumps(obj: Any) -> str:
    """Serialize object to canonical JSON string: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_sha256(data_bytes: bytes) -> str:
    """Compute hex SHA-256 digest."""
    return hashlib.sha256(data_bytes).hexdigest()


def compute_entity_hash(records: Iterable[Dict[str, Any]], sort_key: str) -> str:
    """Compute canonical SHA-256 hash for an iterable of dictionary records."""
    hasher = hashlib.sha256()
    sorted_records = sorted(records, key=lambda r: r[sort_key])
    for rec in sorted_records:
        line = canonical_json_dumps(rec) + "\n"
        hasher.update(line.encode("utf-8"))
    return hasher.hexdigest()


def compute_items_hash(items: Iterable[Dict[str, Any]]) -> str:
    """Compute canonical SHA-256 hash for items sorted by (order_id, line_no)."""
    hasher = hashlib.sha256()
    sorted_items = sorted(items, key=lambda it: (it["order_id"], it["line_no"]))
    for it in sorted_items:
        line = canonical_json_dumps(it) + "\n"
        hasher.update(line.encode("utf-8"))
    return hasher.hexdigest()


def validate_dataset(
    customers: List[Dict[str, Any]],
    products: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    order_items: List[Dict[str, Any]],
) -> IntegrityReport:
    """Perform rigorous validation of entire dataset."""
    errors: List[str] = []

    # 1. Customer validation & uniqueness
    customer_ids: Set[int] = set()
    for c in customers:
        cid = c["customer_id"]
        if cid in customer_ids:
            errors.append(f"DATA-05: Duplicate customer_id: {cid}")
        customer_ids.add(cid)
        if not c.get("name") or not c.get("city_code"):
            errors.append(f"Customer {cid} has empty name or city_code")

    # 2. Product validation & uniqueness
    product_ids: Set[int] = set()
    product_price_map: Dict[int, int] = {}
    for p in products:
        pid = p["product_id"]
        if pid in product_ids:
            errors.append(f"DATA-05: Duplicate product_id: {pid}")
        product_ids.add(pid)
        price = p.get("base_price_minor", 0)
        if price < 0:
            errors.append(f"DATA-05: Product {pid} has negative base_price_minor: {price}")
        product_price_map[pid] = price

    # 3. Order Items mapping and checks
    items_by_order: Dict[int, List[Dict[str, Any]]] = {}
    item_compound_keys: Set[Tuple[int, int]] = set()

    for item in order_items:
        oid = item["order_id"]
        line_no = item["line_no"]
        pid = item["product_id"]
        qty = item["quantity"]
        unit_price = item["unit_price_minor"]

        # Duplicate compound PK (order_id, line_no)
        if (oid, line_no) in item_compound_keys:
            errors.append(f"DATA-05: Duplicate order_item compound PK ({oid}, {line_no})")
        item_compound_keys.add((oid, line_no))

        # Check positive constraints
        if line_no <= 0:
            errors.append(f"DATA-05: Non-positive line_no {line_no} in order {oid}")
        if qty <= 0:
            errors.append(f"DATA-05: Non-positive quantity {qty} in order {oid}, line {line_no}")
        if unit_price < 0:
            errors.append(f"DATA-05: Negative unit_price_minor {unit_price} in order {oid}, line {line_no}")

        # Foreign key: product_id must exist
        if pid not in product_ids:
            errors.append(f"DATA-04: Foreign key violation: item in order {oid} references non-existent product {pid}")

        items_by_order.setdefault(oid, []).append(item)

    # 4. Order validation & totals calculation
    order_ids: Set[int] = set()
    total_revenue = 0

    for o in orders:
        oid = o["order_id"]
        cid = o["customer_id"]
        total_minor = o["total_minor"]
        status = o["status"]

        if oid in order_ids:
            errors.append(f"DATA-05: Duplicate order_id: {oid}")
        order_ids.add(oid)

        if total_minor < 0:
            errors.append(f"DATA-05: Order {oid} has negative total_minor: {total_minor}")

        if status not in ("pending", "paid", "shipped", "cancelled"):
            errors.append(f"Order {oid} has invalid status: {status}")

        # Foreign key: customer_id must exist
        if cid not in customer_ids:
            errors.append(f"DATA-04: Foreign key violation: order {oid} references non-existent customer {cid}")

        # Check items presence and line_no ordering
        lines = items_by_order.get(oid, [])
        if not lines:
            errors.append(f"DATA-04: Order {oid} has no items")
        else:
            sorted_lines = sorted(lines, key=lambda l: l["line_no"])
            calculated_total = sum(l["quantity"] * l["unit_price_minor"] for l in sorted_lines)
            if calculated_total != total_minor:
                errors.append(
                    f"DATA-04: Total mismatch for order {oid}: header={total_minor}, items_sum={calculated_total}"
                )

            # Check consecutive line numbers: 1, 2, ..., N
            expected_line = 1
            for l in sorted_lines:
                if l["line_no"] != expected_line:
                    errors.append(f"Order {oid} line numbers non-contiguous: expected {expected_line}, got {l['line_no']}")
                expected_line += 1

        total_revenue += total_minor

    # Check for orphan order_items (order_id does not exist in orders)
    for oid in items_by_order:
        if oid not in order_ids:
            errors.append(f"DATA-04: Orphan items found for non-existent order {oid}")

    # Compute Canonical Checksums
    cust_hash = compute_entity_hash(customers, "customer_id")
    prod_hash = compute_entity_hash(products, "product_id")
    ord_hash = compute_entity_hash(orders, "order_id")
    item_hash = compute_items_hash(order_items)

    combined_input = f"{cust_hash}:{prod_hash}:{ord_hash}:{item_hash}"
    overall_hash = compute_sha256(combined_input.encode("utf-8"))

    return IntegrityReport(
        is_valid=(len(errors) == 0),
        total_customers=len(customers),
        total_products=len(products),
        total_orders=len(orders),
        total_items=len(order_items),
        total_revenue_minor=total_revenue,
        checksum_sha256=overall_hash,
        entity_checksums={
            "customers": cust_hash,
            "products": prod_hash,
            "orders": ord_hash,
            "order_items": item_hash,
        },
        errors=errors,
    )


def flatten_embedded_orders(
    embedded_orders: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Flatten Track B embedded orders into Track A orders and items representation."""
    flat_orders: List[Dict[str, Any]] = []
    flat_items: List[Dict[str, Any]] = []

    for eo in embedded_orders:
        oid = eo["order_id"] if "order_id" in eo else eo["_id"]
        order_dict = {
            "order_id": oid,
            "customer_id": eo["customer_id"],
            "order_date": eo["order_date"],
            "status": eo["status"],
            "total_minor": eo["total_minor"],
        }
        flat_orders.append(order_dict)

        for item in eo.get("items", []):
            flat_items.append({
                "order_id": oid,
                "line_no": item["line_no"],
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "unit_price_minor": item["unit_price_minor"],
            })

    return flat_orders, flat_items
