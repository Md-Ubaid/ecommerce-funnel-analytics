-- OLIST STAR SCHEMA
-- fact_orders is the central fact table

-- Drop in reverse dependency order (safe re-runs)

DROP TABLE IF EXISTS fact_orders CASCADE;
DROP TABLE IF EXISTS dim_customers CASCADE;
DROP TABLE IF EXISTS dim_products CASCADE;
DROP TABLE IF EXISTS dim_sellers CASCADE;
DROP TABLE IF EXISTS dim_payments CASCADE;


-- DIMENSION: Customers

CREATE TABLE dim_customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_unique_id VARCHAR(50) NOT NULL,
    customer_city VARCHAR(100),
    customer_state CHAR(2)
);


-- DIMENSION: Products

CREATE TABLE dim_products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_category_en VARCHAR(100),        -- translated name
    product_weight_g NUMERIC(10,2),
    product_length_cm NUMERIC(10,2),
    product_height_cm NUMERIC(10,2),
    product_width_cm NUMERIC(10,2)
);


-- DIMENSION: Sellers

CREATE TABLE dim_sellers (
    seller_id VARCHAR(50) PRIMARY KEY,
    seller_city VARCHAR(100),
    seller_state CHAR(2)
);


-- DIMENSION: Payments
-- (one order can have multiple payment rows — store at order level)

CREATE TABLE dim_payments (
    order_id VARCHAR(50) PRIMARY KEY,
    payment_type VARCHAR(50),
    payment_installments INT,
    payment_value NUMERIC(10,2)
);


-- FACT: Orders

CREATE TABLE fact_orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES dim_customers(customer_id),
    product_id VARCHAR(50) REFERENCES dim_products(product_id),
    seller_id VARCHAR(50) REFERENCES dim_sellers(seller_id),

    -- Order lifecycle timestamps
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,

    -- Status (used for funnel analysis)
    order_status VARCHAR(50),

    -- Financials
    price NUMERIC(10,2),
    freight_value NUMERIC(10,2),
    order_revenue NUMERIC(10,2),             -- price + freight

    -- Derived time fields (for BI slicing)
    purchase_year INT,
    purchase_month INT,
    purchase_day_of_week INT,               -- 0=Mon, 6=Sun
    delivery_delay_days NUMERIC(10,2),      -- actual - estimated

    -- Review
    review_score INT
);

-- Indexes for common query patterns
CREATE INDEX idx_fact_orders_customer ON fact_orders(customer_id);
CREATE INDEX idx_fact_orders_product ON fact_orders(product_id);
CREATE INDEX idx_fact_orders_status ON fact_orders(order_status);
CREATE INDEX idx_fact_orders_purchase ON fact_orders(order_purchase_timestamp);