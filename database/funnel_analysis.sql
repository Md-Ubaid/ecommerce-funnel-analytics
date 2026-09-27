-- FUNNEL ANALYSIS — Olist Order Lifecycle
-- Funnel stages derived from order_status field


-- Q1: Funnel Stage Conversion Rates
-- Shows how many orders make it through each lifecycle stage and the drop-off % between stages

WITH funnel_stages AS (
    SELECT
        COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE order_status != 'created') AS approved,
        COUNT(*) FILTER (WHERE order_status IN (
            'invoiced','processing','shipped',
            'delivered','canceled')) AS invoiced,
        COUNT(*) FILTER (WHERE order_status IN (
            'processing','shipped','delivered','canceled')) AS processing,
        COUNT(*) FILTER (WHERE order_status IN (
            'shipped','delivered','canceled')) AS shipped,
        COUNT(*) FILTER (WHERE order_status = 'delivered') AS delivered
    FROM fact_orders
)
SELECT
    stage,
    cnt,
    ROUND(cnt * 100.0 / total_orders, 2) AS conversion_pct,
    ROUND((LAG(cnt) OVER (ORDER BY step) - cnt) * 100.0
    / NULLIF(LAG(cnt) OVER (ORDER BY step), 0), 2) AS dropoff_pct
FROM (
    SELECT 1 AS step, 'created' AS stage, total_orders  AS cnt, total_orders FROM funnel_stages
    UNION ALL
    SELECT 2, 'approved', approved, total_orders FROM funnel_stages
    UNION ALL
    SELECT 3, 'invoiced', invoiced, total_orders FROM funnel_stages
    UNION ALL
    SELECT 4, 'processing', processing, total_orders FROM funnel_stages
    UNION ALL
    SELECT 5, 'shipped', shipped, total_orders FROM funnel_stages
    UNION ALL
    SELECT 6, 'delivered', delivered, total_orders FROM funnel_stages
) ranked
ORDER BY step;



-- Q2: Revenue Leakage Per Stage
-- GMV lost at each drop-off point

WITH stage_revenue AS (
    SELECT
        order_status,
        COUNT(*) AS order_count,
        ROUND(SUM(order_revenue)::NUMERIC, 2) AS gmv
    FROM fact_orders
    WHERE order_status NOT IN ('delivered', 'shipped', 'processing',
                                'invoiced', 'approved', 'created')
       OR order_status IS NOT NULL
    GROUP BY order_status
),
total AS (
    SELECT SUM(order_revenue) AS total_gmv FROM fact_orders
)
SELECT
    s.order_status,
    s.order_count,
    s.gmv AS stage_gmv,
    ROUND(s.gmv * 100.0 / t.total_gmv, 2) AS pct_of_total_gmv,
    ROUND(s.gmv / NULLIF(s.order_count, 0), 2) AS avg_order_value
FROM stage_revenue s, total t
ORDER BY s.gmv DESC;


-- ------------------------------------------------------------
-- Q3: Drop-off by State and Product Category
-- Identifies which segments drive the most cancellations
-- ------------------------------------------------------------

-- Top 10 states by cancellation rate
SELECT
    c.customer_state,
    COUNT(*)  AS total_orders,
    COUNT(*) FILTER (WHERE f.order_status = 'canceled') AS canceled_orders,
    ROUND(COUNT(*) FILTER (WHERE f.order_status = 'canceled')
          * 100.0 / COUNT(*), 2) AS cancel_rate_pct,
    ROUND(SUM(CASE WHEN f.order_status = 'canceled'
              THEN f.order_revenue ELSE 0 END)::NUMERIC, 2) AS canceled_gmv
FROM fact_orders f
JOIN dim_customers c USING (customer_id)
GROUP BY c.customer_state
HAVING COUNT(*) > 100          -- exclude states with too few orders
ORDER BY cancel_rate_pct DESC
LIMIT 10;

-- Top 10 product categories by cancellation rate
SELECT
    COALESCE(p.product_category_en, 'unknown') AS category,
    COUNT(*)  AS total_orders,
    COUNT(*) FILTER (WHERE f.order_status = 'canceled') AS canceled_orders,
    ROUND(COUNT(*) FILTER (WHERE f.order_status = 'canceled')
          * 100.0 / COUNT(*), 2) AS cancel_rate_pct
FROM fact_orders f
JOIN dim_products p USING (product_id)
GROUP BY p.product_category_en
HAVING COUNT(*) > 50
ORDER BY cancel_rate_pct DESC
LIMIT 10;

-- Q4 — Monthly Cohort Order Counts
SELECT
    TO_CHAR(DATE_TRUNC('month', order_purchase_timestamp), 'YYYY-MM') AS order_month,
    COUNT(*) AS total_orders,
    COUNT(DISTINCT customer_id) AS unique_customers,
    ROUND(SUM(order_revenue)::NUMERIC, 2) AS monthly_gmv,
    ROUND(AVG(order_revenue)::NUMERIC, 2) AS avg_order_value
FROM fact_orders
WHERE order_purchase_timestamp IS NOT NULL
  AND order_status = 'delivered'
GROUP BY DATE_TRUNC('month', order_purchase_timestamp)
ORDER BY DATE_TRUNC('month', order_purchase_timestamp);


-- Q5 — Delivery Delay by Seller State
SELECT
    s.seller_state,
    COUNT(*) AS total_orders,
    ROUND(AVG(f.delivery_delay_days)::NUMERIC, 2) AS avg_delay_days,
    ROUND(MIN(f.delivery_delay_days)::NUMERIC, 2) AS earliest_days,
    ROUND(MAX(f.delivery_delay_days)::NUMERIC, 2) AS worst_delay_days,
    COUNT(*) FILTER (WHERE f.delivery_delay_days > 0) AS late_deliveries,
    ROUND(COUNT(*) FILTER (WHERE f.delivery_delay_days > 0)
          * 100.0 / COUNT(*), 2) AS late_pct
FROM fact_orders f
JOIN dim_sellers s USING (seller_id)
WHERE f.order_status = 'delivered'
  AND f.delivery_delay_days IS NOT NULL
GROUP BY s.seller_state
HAVING COUNT(*) > 100
ORDER BY avg_delay_days DESC
LIMIT 10;