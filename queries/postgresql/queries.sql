-- =============================================================================
-- BenchLab Standard Query Catalog for PostgreSQL (Track A)
-- Strictly implements SPEC.md Section 5
-- =============================================================================

-- Q1: Point lookup by order_id
-- Parameters: %(order_id)s
-- Expected: 0 or 1 row
-- name: q1_point_lookup
SELECT order_id, customer_id, order_date, status, total_minor
FROM orders
WHERE order_id = %(order_id)s;

-- Q2: Recent orders for a customer (limit 50)
-- Parameters: %(customer_id)s
-- name: q2_customer_orders
SELECT order_id, customer_id, order_date, status, total_minor
FROM orders
WHERE customer_id = %(customer_id)s
ORDER BY order_date DESC, order_id DESC
LIMIT 50;

-- Q3: Filter orders by status and date range [from_ts, to_ts) (limit 100)
-- Parameters: %(status)s, %(from_ts)s, %(to_ts)s
-- name: q3_status_date_filter
SELECT order_id, customer_id, order_date, status, total_minor
FROM orders
WHERE status = %(status)s
  AND order_date >= %(from_ts)s
  AND order_date < %(to_ts)s
ORDER BY order_date DESC, order_id DESC
LIMIT 100;

-- Q4: Exact count of orders by status and date range
-- Parameters: %(status)s, %(from_ts)s, %(to_ts)s
-- name: q4_exact_count
SELECT COUNT(*) AS order_count
FROM orders
WHERE status = %(status)s
  AND order_date >= %(from_ts)s
  AND order_date < %(to_ts)s;

-- Q5: Monthly revenue and order count for 'paid' orders
-- Parameters: %(from_ts)s, %(to_ts)s
-- name: q5_monthly_revenue
SELECT to_char(date_trunc('month', order_date AT TIME ZONE 'UTC'), 'YYYY-MM-01T00:00:00.000Z') AS month_utc,
       COUNT(*) AS order_count,
       COALESCE(SUM(total_minor), 0)::BIGINT AS revenue_minor
FROM orders
WHERE status = 'paid'
  AND order_date >= %(from_ts)s
  AND order_date < %(to_ts)s
GROUP BY date_trunc('month', order_date AT TIME ZONE 'UTC')
ORDER BY month_utc ASC;

-- Q6: Top 10 customers by revenue for 'paid' orders in date range
-- Parameters: %(from_ts)s, %(to_ts)s
-- name: q6_top_customers
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

-- Q7_offset: Deep pagination using OFFSET
-- Parameters: %(offset)s
-- name: q7_offset
SELECT order_id, customer_id, order_date, status, total_minor
FROM orders
ORDER BY order_date DESC, order_id DESC
LIMIT 50 OFFSET %(offset)s;

-- Q7_keyset: Keyset pagination using composite anchor (order_date, order_id)
-- Parameters: %(last_order_date)s, %(last_order_id)s
-- name: q7_keyset
SELECT order_id, customer_id, order_date, status, total_minor
FROM orders
WHERE (%(last_order_date)s::TIMESTAMPTZ IS NULL)
   OR (order_date < %(last_order_date)s::TIMESTAMPTZ)
   OR (order_date = %(last_order_date)s::TIMESTAMPTZ AND order_id < %(last_order_id)s)
ORDER BY order_date DESC, order_id DESC
LIMIT 50;

-- Q8_track_a: Single order with line items joined (Track A Normalized)
-- Parameters: %(order_id)s
-- name: q8_track_a
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
