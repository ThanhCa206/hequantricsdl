"""Query Correctness and Equivalence Verification Suite (Phase 3 Gate G3).
Strictly implements SPEC.md Section 5 & Section 12 (QUERY-01 -> QUERY-07):
- QUERY-01: Q1–Q8 results on fixture dataset match independent Python Oracle and match between PG and Mongo.
- QUERY-02: Non-existent ID, empty filters return empty list or 0 count as per contract.
- QUERY-03: Date range [from_ts, to_ts) includes from, excludes to, strictly in UTC.
- QUERY-04: Tie-breaking sorts (order_date DESC, order_id DESC; revenue DESC, customer_id ASC) are stable.
- QUERY-05: Q5 and Q6 aggregations do NOT multiply order revenue by number of items.
- QUERY-06: Q7 offset and keyset pagination on same anchor return identical 50 records in identical order.
- QUERY-07: Q8 Track A (normalized JOIN / $lookup) and Track B (embedded document) are 100% equivalent.
"""

from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from app.adapters import MongoAdapter, PostgresAdapter
from app.datasets.generator import DataGenerator
from app.domain.query_catalog import (
    POSTGRES_QUERIES,
    QUERY_SPECS,
    generate_parameter_pool,
)
from app.main import app
from configs.profiles import load_profile
from tests.correctness.oracle import PythonOracle

client = TestClient(app)


@pytest.fixture(scope="module")
def adapters():
    """Instantiate live Postgres and Mongo adapters."""
    pg = PostgresAdapter()
    mg = MongoAdapter()
    yield {"pg": pg, "mg": mg}
    pg.close()
    mg.close()


@pytest.fixture(scope="module")
def fixture_data_and_oracle(adapters):
    """Generate in-memory fixture dataset and instantiate independent Python Oracle."""
    from app.datasets.loader import DatasetLoader

    profile = load_profile("fixture")
    gen = DataGenerator(profile=profile, seed=42)

    # Ensure live databases have the fixture dataset loaded cleanly
    DatasetLoader.load_postgres(adapters["pg"], gen, truncate_first=True)
    DatasetLoader.load_mongo(adapters["mg"], gen, truncate_first=True)

    # Regenerate in-memory generator stream for independent oracle
    gen = DataGenerator(profile=profile, seed=42)
    customers = [c.to_dict() for c in next(gen.stream_customers(batch_size=1000))]
    products = [p.to_dict() for p in next(gen.stream_products(batch_size=1000))]

    orders: List[Dict[str, Any]] = []
    order_items: List[Dict[str, Any]] = []
    for ord_batch, it_batch, _ in gen.stream_orders(batch_size=1000):
        orders.extend([o.to_dict() for o in ord_batch])
        order_items.extend([it.to_dict() for it in it_batch])

    oracle = PythonOracle(
        customers=customers,
        products=products,
        orders=orders,
        order_items=order_items,
    )
    return {
        "profile": profile,
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "oracle": oracle,
    }


def test_query_01_all_queries_on_fixture_match_oracle_and_engines(fixture_data_and_oracle, adapters):
    """QUERY-01: Q1–Q8 on fixture match independent Python Oracle and match between PostgreSQL and MongoDB."""
    oracle: PythonOracle = fixture_data_and_oracle["oracle"]
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    # 1. Q1: Point lookup on existing order
    q1_params = {"order_id": 1}
    oracle_q1 = oracle.execute("Q1", q1_params)
    pg_q1 = pg.execute("Q1", q1_params).data
    mg_q1 = mg.execute("Q1", q1_params).data
    assert pg_q1 == oracle_q1, f"Q1 PG mismatch with Oracle: {pg_q1} != {oracle_q1}"
    assert mg_q1 == oracle_q1, f"Q1 MG mismatch with Oracle: {mg_q1} != {oracle_q1}"

    # 2. Q2: Customer orders
    q2_params = {"customer_id": 5}
    oracle_q2 = oracle.execute("Q2", q2_params)
    pg_q2 = pg.execute("Q2", q2_params).data
    mg_q2 = mg.execute("Q2", q2_params).data
    assert pg_q2 == oracle_q2
    assert mg_q2 == oracle_q2

    # 3. Q3: Status and date range
    q3_params = {
        "status": "shipped",
        "from_ts": "2023-01-01T00:00:00.000Z",
        "to_ts": "2024-01-01T00:00:00.000Z",
    }
    oracle_q3 = oracle.execute("Q3", q3_params)
    pg_q3 = pg.execute("Q3", q3_params).data
    mg_q3 = mg.execute("Q3", q3_params).data
    assert pg_q3 == oracle_q3
    assert mg_q3 == oracle_q3

    # 4. Q4: Exact count
    q4_params = {
        "status": "shipped",
        "from_ts": "2023-01-01T00:00:00.000Z",
        "to_ts": "2024-01-01T00:00:00.000Z",
    }
    oracle_q4 = oracle.execute("Q4", q4_params)
    pg_q4 = pg.execute("Q4", q4_params).data
    mg_q4 = mg.execute("Q4", q4_params).data
    assert pg_q4 == oracle_q4
    assert mg_q4 == oracle_q4

    # 5. Q5: Monthly revenue
    q5_params = {
        "from_ts": "2023-01-01T00:00:00.000Z",
        "to_ts": "2024-01-01T00:00:00.000Z",
    }
    oracle_q5 = oracle.execute("Q5", q5_params)
    pg_q5 = pg.execute("Q5", q5_params).data
    mg_q5 = mg.execute("Q5", q5_params).data
    assert pg_q5 == oracle_q5
    assert mg_q5 == oracle_q5

    # 6. Q6: Top 10 customers
    q6_params = {
        "from_ts": "2023-01-01T00:00:00.000Z",
        "to_ts": "2024-01-01T00:00:00.000Z",
    }
    oracle_q6 = oracle.execute("Q6", q6_params)
    pg_q6 = pg.execute("Q6", q6_params).data
    mg_q6 = mg.execute("Q6", q6_params).data
    assert pg_q6 == oracle_q6
    assert mg_q6 == oracle_q6

    # 7. Q7: Offset pagination
    q7_params = {"offset": 10}
    oracle_q7 = oracle.execute("Q7_offset", q7_params)
    pg_q7 = pg.execute("Q7_offset", q7_params).data
    mg_q7 = mg.execute("Q7_offset", q7_params).data
    assert pg_q7 == oracle_q7
    assert mg_q7 == oracle_q7

    # 8. Q8 Track A and Track B
    q8_params = {"order_id": 1}
    oracle_q8 = oracle.execute("Q8", q8_params)
    pg_q8_a = pg.execute("Q8_track_a", q8_params).data
    mg_q8_a = mg.execute("Q8_track_a", q8_params).data
    mg_q8_b = mg.execute("Q8_track_b", q8_params).data
    assert pg_q8_a == oracle_q8
    assert mg_q8_a == oracle_q8
    assert mg_q8_b == oracle_q8


def test_query_02_empty_results_and_non_existent_id(adapters):
    """QUERY-02: Non-existent ID, empty filters return empty list or 0 count as per contract."""
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    # Non-existent order_id (e.g. 999999)
    bad_id_params = {"order_id": 999999}
    pg_res = pg.execute("Q1", bad_id_params)
    mg_res = mg.execute("Q1", bad_id_params)
    assert pg_res.data == []
    assert mg_res.data == []
    assert pg_res.row_count == 0
    assert mg_res.row_count == 0

    # Non-existent customer_id in Q2
    pg_q2 = pg.execute("Q2", {"customer_id": 999999})
    mg_q2 = mg.execute("Q2", {"customer_id": 999999})
    assert pg_q2.data == []
    assert mg_q2.data == []

    # Q4 count with future date range yielding 0 results
    empty_date_params = {
        "status": "paid",
        "from_ts": "2099-01-01T00:00:00.000Z",
        "to_ts": "2099-02-01T00:00:00.000Z",
    }
    pg_count = pg.execute("Q4", empty_date_params).data
    mg_count = mg.execute("Q4", empty_date_params).data
    assert pg_count == [{"order_count": 0}]
    assert mg_count == [{"order_count": 0}]


def test_query_03_date_boundary_half_open_interval(adapters):
    """QUERY-03: Date range [from_ts, to_ts) includes from, excludes to, strictly in UTC."""
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    # Order 1 date: '2023-10-13T08:28:14.292Z'
    # Exactly matching from_ts -> should be included
    inclusive_from = {
        "status": "shipped",
        "from_ts": "2023-10-13T08:28:14.292Z",
        "to_ts": "2023-10-14T00:00:00.000Z",
    }
    pg_inc = pg.execute("Q3", inclusive_from).data
    mg_inc = mg.execute("Q3", inclusive_from).data
    assert any(o["order_id"] == 1 for o in pg_inc)
    assert any(o["order_id"] == 1 for o in mg_inc)

    # Exactly matching to_ts -> should be EXCLUDED
    exclusive_to = {
        "status": "shipped",
        "from_ts": "2023-10-01T00:00:00.000Z",
        "to_ts": "2023-10-13T08:28:14.292Z",
    }
    pg_exc = pg.execute("Q3", exclusive_to).data
    mg_exc = mg.execute("Q3", exclusive_to).data
    assert not any(o["order_id"] == 1 for o in pg_exc)
    assert not any(o["order_id"] == 1 for o in mg_exc)


def test_query_04_tie_breaking_sort_stability(adapters):
    """QUERY-04: Tie-breaking sorts (order_date DESC, order_id DESC; revenue DESC, customer_id ASC) are stable."""
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    # Q6 Top customers tie breaking by customer_id ASC
    q6_params = {
        "from_ts": "2020-01-01T00:00:00.000Z",
        "to_ts": "2030-01-01T00:00:00.000Z",
    }
    pg_q6 = pg.execute("Q6", q6_params).data
    mg_q6 = mg.execute("Q6", q6_params).data
    assert len(pg_q6) > 0
    assert pg_q6 == mg_q6

    # Verify descending revenue order
    for i in range(len(pg_q6) - 1):
        r1, r2 = pg_q6[i]["revenue_minor"], pg_q6[i + 1]["revenue_minor"]
        assert r1 >= r2
        if r1 == r2:
            assert pg_q6[i]["customer_id"] < pg_q6[i + 1]["customer_id"]


def test_query_05_no_revenue_duplication_on_aggregations(fixture_data_and_oracle, adapters):
    """QUERY-05: Q5 and Q6 aggregations do NOT multiply order revenue by number of items."""
    oracle: PythonOracle = fixture_data_and_oracle["oracle"]
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    # Total revenue for paid orders in 2023
    params = {
        "from_ts": "2023-01-01T00:00:00.000Z",
        "to_ts": "2024-01-01T00:00:00.000Z",
    }
    pg_q5 = pg.execute("Q5", params).data
    mg_q5 = mg.execute("Q5", params).data
    oracle_q5 = oracle.execute("Q5", params)

    total_pg = sum(m["revenue_minor"] for m in pg_q5)
    total_mg = sum(m["revenue_minor"] for m in mg_q5)
    total_oracle = sum(m["revenue_minor"] for m in oracle_q5)

    assert total_pg == total_oracle
    assert total_mg == total_oracle

    # Verify that total revenue matches header sums directly, not header * items
    paid_orders = [
        o for o in fixture_data_and_oracle["orders"]
        if o["status"] == "paid" and "2023-01-01" <= o["order_date"] < "2024-01-01"
    ]
    raw_header_sum = sum(o["total_minor"] for o in paid_orders)
    assert total_pg == raw_header_sum


def test_query_06_q7_offset_and_keyset_anchor_equivalence(adapters):
    """QUERY-06: Q7 offset and keyset pagination on same anchor return identical 50 records in identical order."""
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    # First page via offset=0
    pg_p1 = pg.execute("Q7_offset", {"offset": 0}).data
    mg_p1 = mg.execute("Q7_offset", {"offset": 0}).data
    assert pg_p1 == mg_p1

    if len(pg_p1) > 10:
        # Take the 10th order as anchor for keyset
        anchor_order = pg_p1[9]
        anchor_ts = anchor_order["order_date"]
        anchor_id = anchor_order["order_id"]

        keyset_params = {
            "last_order_date": anchor_ts,
            "last_order_id": anchor_id,
        }
        pg_keyset = pg.execute("Q7_keyset", keyset_params).data
        mg_keyset = mg.execute("Q7_keyset", keyset_params).data
        assert pg_keyset == mg_keyset

        # Offset=10 should match keyset after 10th record
        pg_offset10 = pg.execute("Q7_offset", {"offset": 10}).data
        assert pg_keyset == pg_offset10


def test_query_07_q8_track_a_and_track_b_complete_equivalence(adapters):
    """QUERY-07: Q8 Track A (normalized JOIN / $lookup) and Track B (embedded document) are 100% equivalent."""
    pg: PostgresAdapter = adapters["pg"]
    mg: MongoAdapter = adapters["mg"]

    for oid in [1, 2, 5, 10, 25]:
        params = {"order_id": oid}
        pg_a = pg.execute("Q8_track_a", params).data
        mg_a = mg.execute("Q8_track_a", params).data
        mg_b = mg.execute("Q8_track_b", params).data

        assert pg_a == mg_a, f"Track A mismatch for order {oid}"
        assert pg_a == mg_b, f"Track A vs Track B mismatch for order {oid}"
        assert len(pg_a) == 1
        # Check structure
        order_doc = pg_a[0]
        assert "items" in order_doc
        assert len(order_doc["items"]) > 0
        # Line numbers ordered ascending 1, 2, ...
        line_nos = [it["line_no"] for it in order_doc["items"]]
        assert line_nos == sorted(line_nos)


def test_queries_api_endpoints():
    """Verify REST API endpoints: GET /api/queries, POST /execute, POST /explain, GET /params."""
    # 1. GET /api/queries
    res = client.get("/api/queries")
    assert res.status_code == 200
    queries = res.json()
    assert len(queries) >= 8
    q_ids = [q["query_id"] for q in queries]
    assert "Q1" in q_ids
    assert "Q8_track_a" in q_ids
    assert "Q8_track_b" in q_ids

    # 2. GET /api/queries/Q1
    res = client.get("/api/queries/Q1")
    assert res.status_code == 200
    assert res.json()["query_id"] == "Q1"

    # 3. GET /api/queries/Q1/params
    res = client.get("/api/queries/Q1/params?profile=fixture&count=10")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 10
    assert len(data["parameters"]) == 10

    # 4. POST /api/queries/Q1/execute
    exec_payload = {
        "engine": "both",
        "params": {"order_id": 1},
        "timed": True,
    }
    res = client.post("/api/queries/Q1/execute", json=exec_payload)
    assert res.status_code == 200
    exec_data = res.json()
    assert exec_data["is_equivalent"] is True
    assert "postgresql" in exec_data["results"]
    assert "mongodb" in exec_data["results"]
    assert exec_data["results"]["postgresql"]["execution_time_ms"] >= 0
    assert exec_data["results"]["mongodb"]["execution_time_ms"] >= 0

    # 5. POST /api/queries/Q1/explain (PostgreSQL)
    explain_pg = client.post("/api/queries/Q1/explain", json={"engine": "postgresql", "params": {"order_id": 1}})
    assert explain_pg.status_code == 200
    assert explain_pg.json()["engine"] == "postgresql"
    assert "raw_plan" in explain_pg.json()

    # 6. POST /api/queries/Q1/explain (MongoDB)
    explain_mg = client.post("/api/queries/Q1/explain", json={"engine": "mongodb", "params": {"order_id": 1}})
    assert explain_mg.status_code == 200
    assert explain_mg.json()["engine"] == "mongodb"
    assert "raw_plan" in explain_mg.json()
