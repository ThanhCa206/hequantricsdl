-- =============================================================================
-- PostgreSQL DDL Schema for BenchLab
-- Track A (Normalized Reference Model)
-- Conforms to SPEC.md Section 4.4
-- =============================================================================

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- 1. Customers Table
CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- 2. Products Table
CREATE TABLE products (
    product_id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_code VARCHAR(20) NOT NULL,
    base_price_minor BIGINT NOT NULL CHECK (base_price_minor >= 0)
);

-- 3. Orders Table
CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    order_date TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    total_minor BIGINT NOT NULL CHECK (total_minor >= 0)
);

-- 4. Order Items Table
CREATE TABLE order_items (
    order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    product_id BIGINT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price_minor BIGINT NOT NULL CHECK (unit_price_minor >= 0),
    PRIMARY KEY (order_id, line_no)
);
