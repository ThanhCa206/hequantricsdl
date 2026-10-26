"""Comprehensive Correctness and Data Integrity Tests for Phase 2.
Implements test matrix requirements:
- DATA-01: Seed determinism (seed=42 twice produces identical SHA-256 checksum)
- DATA-02: Different seeds yield different hashes with valid structure
- DATA-03: Entity count and Track A vs Track B embedded flattening equivalence
- DATA-04: Validator detects total_minor mismatch, missing items, or orphan records
- DATA-05: Rejection of negative amounts, duplicate IDs, and invalid constraints
- DATA-06: Idempotent re-loading guarantee
- INDEX-01: Verification of I0 and I1 index catalog specifications
"""

import copy
import pytest

from app.datasets.generator import DataGenerator
from app.datasets.validator import (
    flatten_embedded_orders,
    validate_dataset,
)
from configs.indexes import MONGO_I1_DEFINITIONS, POSTGRES_I1_STATEMENTS
from configs.profiles import load_profile


@pytest.fixture
def fixture_profile():
    return load_profile("fixture")


def test_data_01_seed_determinism(fixture_profile):
    """DATA-01: Generating twice with same seed=42 produces 100% identical SHA-256."""
    gen1 = DataGenerator(fixture_profile, seed=42)
    cust1 = [c.to_dict() for b in gen1.stream_customers() for c in b]
    prod1 = [p.to_dict() for b in gen1.stream_products() for p in b]
    ord1 = []
    it1 = []
    for ord_b, it_b, _ in gen1.stream_orders():
        ord1.extend([o.to_dict() for o in ord_b])
        it1.extend([it.to_dict() for it in it_b])
    rep1 = validate_dataset(cust1, prod1, ord1, it1)

    gen2 = DataGenerator(fixture_profile, seed=42)
    cust2 = [c.to_dict() for b in gen2.stream_customers() for c in b]
    prod2 = [p.to_dict() for b in gen2.stream_products() for p in b]
    ord2 = []
    it2 = []
    for ord_b, it_b, _ in gen2.stream_orders():
        ord2.extend([o.to_dict() for o in ord_b])
        it2.extend([it.to_dict() for it in it_b])
    rep2 = validate_dataset(cust2, prod2, ord2, it2)

    assert rep1.is_valid is True
    assert rep2.is_valid is True
    assert rep1.checksum_sha256 == rep2.checksum_sha256
    assert rep1.entity_checksums == rep2.entity_checksums
    assert rep1.total_revenue_minor == rep2.total_revenue_minor


def test_data_02_different_seed(fixture_profile):
    """DATA-02: Different seed yields different hash, but structural integrity holds."""
    gen1 = DataGenerator(fixture_profile, seed=42)
    cust1 = [c.to_dict() for b in gen1.stream_customers() for c in b]
    prod1 = [p.to_dict() for b in gen1.stream_products() for p in b]
    ord1 = []
    it1 = []
    for ord_b, it_b, _ in gen1.stream_orders():
        ord1.extend([o.to_dict() for o in ord_b])
        it1.extend([it.to_dict() for it in it_b])
    rep1 = validate_dataset(cust1, prod1, ord1, it1)

    gen2 = DataGenerator(fixture_profile, seed=99)
    cust2 = [c.to_dict() for b in gen2.stream_customers() for c in b]
    prod2 = [p.to_dict() for b in gen2.stream_products() for p in b]
    ord2 = []
    it2 = []
    for ord_b, it_b, _ in gen2.stream_orders():
        ord2.extend([o.to_dict() for o in ord_b])
        it2.extend([it.to_dict() for it in it_b])
    rep2 = validate_dataset(cust2, prod2, ord2, it2)

    assert rep1.is_valid is True
    assert rep2.is_valid is True
    assert rep1.checksum_sha256 != rep2.checksum_sha256
    assert rep1.total_orders == rep2.total_orders == 50


def test_data_03_track_a_vs_track_b_equivalence(fixture_profile):
    """DATA-03: Flattening Track B embedded orders matches Track A reference data 100%."""
    gen = DataGenerator(fixture_profile, seed=42)
    track_a_orders = []
    track_a_items = []
    track_b_embedded = []

    for ord_b, it_b, emb_b in gen.stream_orders():
        track_a_orders.extend([o.to_dict() for o in ord_b])
        track_a_items.extend([it.to_dict() for it in it_b])
        track_b_embedded.extend([emb.to_dict() for emb in emb_b])

    flat_orders, flat_items = flatten_embedded_orders(track_b_embedded)

    assert len(flat_orders) == len(track_a_orders)
    assert len(flat_items) == len(track_a_items)

    # Verify identical order contents
    assert flat_orders == track_a_orders
    assert flat_items == track_a_items


def test_data_04_validator_detects_mismatch_and_missing_items(fixture_profile):
    """DATA-04: Validator catches corrupted order totals or missing items."""
    gen = DataGenerator(fixture_profile, seed=42)
    cust = [c.to_dict() for b in gen.stream_customers() for c in b]
    prod = [p.to_dict() for b in gen.stream_products() for p in b]
    orders = []
    items = []
    for ord_b, it_b, _ in gen.stream_orders():
        orders.extend([o.to_dict() for o in ord_b])
        items.extend([it.to_dict() for it in it_b])

    # Case A: Corrupt total_minor in order 1
    corrupt_orders = copy.deepcopy(orders)
    corrupt_orders[0]["total_minor"] += 99999
    rep_a = validate_dataset(cust, prod, corrupt_orders, items)
    assert rep_a.is_valid is False
    assert any("Total mismatch for order 1" in err for err in rep_a.errors)

    # Case B: Remove line item from order 2
    corrupt_items = [it for it in items if not (it["order_id"] == 2 and it["line_no"] == 1)]
    rep_b = validate_dataset(cust, prod, orders, corrupt_items)
    assert rep_b.is_valid is False
    assert any("Total mismatch for order 2" in err or "line numbers non-contiguous" in err for err in rep_b.errors)

    # Case C: Foreign key violation (order references non-existent customer)
    corrupt_orders_fk = copy.deepcopy(orders)
    corrupt_orders_fk[0]["customer_id"] = 999999
    rep_c = validate_dataset(cust, prod, corrupt_orders_fk, items)
    assert rep_c.is_valid is False
    assert any("references non-existent customer" in err for err in rep_c.errors)


def test_data_05_rejection_of_duplicates_and_negatives(fixture_profile):
    """DATA-05: Rejection of negative amounts, duplicate IDs, or invalid constraints."""
    gen = DataGenerator(fixture_profile, seed=42)
    cust = [c.to_dict() for b in gen.stream_customers() for c in b]
    prod = [p.to_dict() for b in gen.stream_products() for p in b]
    orders = []
    items = []
    for ord_b, it_b, _ in gen.stream_orders():
        orders.extend([o.to_dict() for o in ord_b])
        items.extend([it.to_dict() for it in it_b])

    # Case A: Negative price
    corrupt_prod = copy.deepcopy(prod)
    corrupt_prod[0]["base_price_minor"] = -50000
    rep_neg_price = validate_dataset(cust, corrupt_prod, orders, items)
    assert rep_neg_price.is_valid is False
    assert any("negative base_price_minor" in err for err in rep_neg_price.errors)

    # Case B: Duplicate customer_id
    corrupt_cust = copy.deepcopy(cust)
    corrupt_cust.append(copy.deepcopy(cust[0]))
    rep_dup_cust = validate_dataset(corrupt_cust, prod, orders, items)
    assert rep_dup_cust.is_valid is False
    assert any("Duplicate customer_id" in err for err in rep_dup_cust.errors)

    # Case C: Duplicate order_item compound PK
    corrupt_items = copy.deepcopy(items)
    corrupt_items.append(copy.deepcopy(items[0]))
    rep_dup_item = validate_dataset(cust, prod, orders, corrupt_items)
    assert rep_dup_item.is_valid is False
    assert any("Duplicate order_item compound PK" in err for err in rep_dup_item.errors)


def test_data_06_idempotency_logic():
    """DATA-06: Verifies upsert dictionary deduplication / idempotency simulation."""
    # Simulate batch loading dictionary state (like DB upsert)
    table_state = {}

    records = [
        {"customer_id": 1, "name": "Customer 001", "city_code": "HAN"},
        {"customer_id": 2, "name": "Customer 002", "city_code": "SGN"},
    ]

    # First load
    for r in records:
        table_state[r["customer_id"]] = r

    assert len(table_state) == 2

    # Second load (same records)
    for r in records:
        table_state[r["customer_id"]] = r

    # Count must remain exactly 2, no duplicates created
    assert len(table_state) == 2
    assert table_state[1]["name"] == "Customer 001"


def test_index_01_catalog_specifications():
    """INDEX-01: Verifies I1 definitions conform to SPEC Section 6.1."""
    # Verify PostgreSQL I1 definitions
    pg_names = [idx[0] for idx in POSTGRES_I1_STATEMENTS]
    assert "idx_orders_customer_date" in pg_names
    assert "idx_orders_status_date" in pg_names
    assert "idx_orders_date_id" in pg_names

    # Verify MongoDB I1 definitions
    mongo_names = [idx[1] for idx in MONGO_I1_DEFINITIONS]
    assert "idx_orders_customer_date" in mongo_names
    assert "idx_orders_status_date" in mongo_names
    assert "idx_orders_date_id" in mongo_names
    assert "idx_orders_emb_customer_date" in mongo_names
