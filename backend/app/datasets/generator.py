"""Streaming deterministic data generator for BenchLab.
Strictly implements SPEC.md Section 4.2 & 4.3:
- Single deterministic source of truth using fixed seed (default=42)
- Fixed date range [2023-01-01T00:00:00.000Z, 2026-01-01T00:00:00.000Z)
- Integer VND currency (1 unit = 1 VND), total_minor = SUM(quantity * unit_price_minor)
- Distinct products per order, line_no starting at 1
- Status distribution: 10% pending, 45% paid, 35% shipped, 10% cancelled
- Batched streaming generators to prevent high RAM consumption
"""

import math
import random
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Tuple

from app.domain.models import (
    CATEGORY_CODES,
    CITY_CODES,
    Customer,
    Order,
    OrderEmbedded,
    OrderItem,
    OrderStatus,
    Product,
    format_utc_iso,
)
from configs.profiles import DatasetProfile

# Fixed timestamp bounds in milliseconds (UTC)
# [2023-01-01T00:00:00.000Z, 2026-01-01T00:00:00.000Z)
DATE_START_MS = int(datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
DATE_END_MS = int(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

CUSTOMER_DATE_START_MS = int(datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
CUSTOMER_DATE_END_MS = int(datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

STATUS_CHOICES: List[OrderStatus] = ["pending", "paid", "shipped", "cancelled"]
STATUS_WEIGHTS = [0.10, 0.45, 0.35, 0.10]


class DataGenerator:
    """Deterministic streaming data generator."""

    def __init__(self, profile: DatasetProfile, seed: int = 42):
        self.profile = profile
        self.seed = seed
        self.rng = random.Random(seed)

    def _ms_to_iso(self, ms: int) -> str:
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        return format_utc_iso(dt)

    def stream_customers(self, batch_size: int = 1000) -> Generator[List[Customer], None, None]:
        """Stream customers in batches with deterministic city assignment and creation timestamp."""
        # Separate sub-seeded RNG for customers
        rng = random.Random(self.seed + 1001)
        batch: List[Customer] = []

        for cid in range(1, self.profile.num_customers + 1):
            # Ensure each of the 10 cities gets representation
            if cid <= len(CITY_CODES):
                city = CITY_CODES[cid - 1]
            else:
                city = rng.choice(CITY_CODES)

            created_ms = rng.randint(CUSTOMER_DATE_START_MS, CUSTOMER_DATE_END_MS - 1)
            customer = Customer(
                customer_id=cid,
                name=f"Customer {cid:06d}",
                city_code=city,
                created_at=self._ms_to_iso(created_ms),
            )
            batch.append(customer)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def stream_products(self, batch_size: int = 1000) -> Generator[List[Product], None, None]:
        """Stream products in batches with deterministic category and price (10k - 5M VND)."""
        rng = random.Random(self.seed + 2002)
        batch: List[Product] = []

        for pid in range(1, self.profile.num_products + 1):
            # Ensure each of the 20 categories gets representation
            if pid <= len(CATEGORY_CODES):
                cat = CATEGORY_CODES[pid - 1]
            else:
                cat = rng.choice(CATEGORY_CODES)

            # Price in minor VND: 10,000 to 5,000,000 VND (steps of 1,000)
            price_steps = rng.randint(10, 5000)
            base_price = price_steps * 1000

            product = Product(
                product_id=pid,
                name=f"Product {pid:06d}",
                category_code=cat,
                base_price_minor=base_price,
            )
            batch.append(product)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def _get_product_price_map(self) -> Dict[int, int]:
        """Precompute product prices deterministically for line item price reference."""
        rng = random.Random(self.seed + 2002)
        price_map: Dict[int, int] = {}
        for pid in range(1, self.profile.num_products + 1):
            price_steps = rng.randint(10, 5000)
            price_map[pid] = price_steps * 1000
        return price_map

    def stream_orders(
        self,
        batch_size: int = 1000,
    ) -> Generator[Tuple[List[Order], List[OrderItem], List[OrderEmbedded]], None, None]:
        """Stream orders, order_items (Track A) and orders_embedded (Track B) in coordinated batches.

        Guarantees total_minor == SUM(quantity * unit_price_minor) of lines.
        """
        rng = random.Random(self.seed + 3003)
        price_map = self._get_product_price_map()

        batch_orders: List[Order] = []
        batch_items: List[OrderItem] = []
        batch_embedded: List[OrderEmbedded] = []

        num_cust = self.profile.num_customers
        num_prod = self.profile.num_products
        min_items = self.profile.min_items_per_order
        max_items = self.profile.max_items_per_order
        is_skewed = (self.profile.distribution == "skewed")

        # 80/20 Pareto distribution setup for skewed mode
        top_20_pct_cust = max(1, int(num_cust * 0.2))

        for oid in range(1, self.profile.num_orders + 1):
            # Select customer
            if is_skewed and rng.random() < 0.80:
                cid = rng.randint(1, top_20_pct_cust)
            else:
                cid = rng.randint(1, num_cust)

            # Order date in [DATE_START_MS, DATE_END_MS)
            order_ms = rng.randint(DATE_START_MS, DATE_END_MS - 1)
            order_date_str = self._ms_to_iso(order_ms)

            # Status with weighted distribution
            status: OrderStatus = rng.choices(STATUS_CHOICES, weights=STATUS_WEIGHTS, k=1)[0]

            # Line items (1 to 5 items)
            num_lines = rng.randint(min_items, max_items)
            # Distinct product IDs for lines in this order
            if num_prod >= num_lines:
                chosen_pids = rng.sample(range(1, num_prod + 1), num_lines)
            else:
                chosen_pids = [rng.randint(1, num_prod) for _ in range(num_lines)]

            order_items_list: List[OrderItem] = []
            embedded_items_list: List[Dict[str, Any]] = []
            order_total_minor = 0

            for line_no, pid in enumerate(chosen_pids, start=1):
                qty = rng.randint(1, 10)
                unit_price = price_map[pid]
                line_total = qty * unit_price
                order_total_minor += line_total

                item = OrderItem(
                    order_id=oid,
                    line_no=line_no,
                    product_id=pid,
                    quantity=qty,
                    unit_price_minor=unit_price,
                )
                order_items_list.append(item)
                embedded_items_list.append({
                    "line_no": line_no,
                    "product_id": pid,
                    "quantity": qty,
                    "unit_price_minor": unit_price,
                })

            order = Order(
                order_id=oid,
                customer_id=cid,
                order_date=order_date_str,
                status=status,
                total_minor=order_total_minor,
            )
            order_emb = OrderEmbedded(
                order_id=oid,
                customer_id=cid,
                order_date=order_date_str,
                status=status,
                total_minor=order_total_minor,
                items=embedded_items_list,
            )

            batch_orders.append(order)
            batch_items.extend(order_items_list)
            batch_embedded.append(order_emb)

            if len(batch_orders) >= batch_size:
                yield (batch_orders, batch_items, batch_embedded)
                batch_orders = []
                batch_items = []
                batch_embedded = []

        if batch_orders:
            yield (batch_orders, batch_items, batch_embedded)
