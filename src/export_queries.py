"""
export_queries.py
-----------------
Exports SQL funnel analysis results to data/processed/ for Power BI.
Run: python3 src/export_queries.py
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

queries = {
    "funnel_conversion": """
        WITH funnel_stages AS (
            SELECT
                COUNT(*)                                            AS total_orders,
                COUNT(*) FILTER (WHERE order_status != 'created')  AS approved,
                COUNT(*) FILTER (WHERE order_status IN (
                    'invoiced','processing','shipped',
                    'delivered','canceled'))                        AS invoiced,
                COUNT(*) FILTER (WHERE order_status IN (
                    'processing','shipped','delivered','canceled')) AS processing,
                COUNT(*) FILTER (WHERE order_status IN (
                    'shipped','delivered','canceled'))              AS shipped,
                COUNT(*) FILTER (WHERE order_status = 'delivered') AS delivered
            FROM fact_orders
        )
        SELECT stage, cnt,
            ROUND(cnt * 100.0 / total_orders, 2) AS conversion_pct,
            ROUND((LAG(cnt) OVER (ORDER BY step) - cnt) * 100.0
                  / NULLIF(LAG(cnt) OVER (ORDER BY step), 0), 2) AS dropoff_pct
        FROM (
            SELECT 1 AS step, 'created'    AS stage, total_orders AS cnt, total_orders FROM funnel_stages
            UNION ALL SELECT 2, 'approved',   approved,   total_orders FROM funnel_stages
            UNION ALL SELECT 3, 'invoiced',   invoiced,   total_orders FROM funnel_stages
            UNION ALL SELECT 4, 'processing', processing, total_orders FROM funnel_stages
            UNION ALL SELECT 5, 'shipped',    shipped,    total_orders FROM funnel_stages
            UNION ALL SELECT 6, 'delivered',  delivered,  total_orders FROM funnel_stages
        ) ranked ORDER BY step
    """,

    "revenue_by_status": """
        WITH total AS (SELECT SUM(order_revenue) AS total_gmv FROM fact_orders)
        SELECT
            order_status,
            COUNT(*)                               AS order_count,
            ROUND(SUM(order_revenue)::NUMERIC, 2) AS stage_gmv,
            ROUND(SUM(order_revenue)*100.0/t.total_gmv, 2) AS pct_of_total_gmv,
            ROUND(AVG(order_revenue)::NUMERIC, 2) AS avg_order_value
        FROM fact_orders, total t
        GROUP BY order_status, t.total_gmv
        ORDER BY stage_gmv DESC
    """,

    "cancellation_by_state": """
        SELECT
            c.customer_state,
            COUNT(*)                                                 AS total_orders,
            COUNT(*) FILTER (WHERE f.order_status = 'canceled')     AS canceled_orders,
            ROUND(COUNT(*) FILTER (WHERE f.order_status = 'canceled')
                  * 100.0 / COUNT(*), 2)                            AS cancel_rate_pct,
            ROUND(SUM(CASE WHEN f.order_status = 'canceled'
                      THEN f.order_revenue ELSE 0 END)::NUMERIC, 2) AS canceled_gmv
        FROM fact_orders f
        JOIN dim_customers c USING (customer_id)
        GROUP BY c.customer_state
        HAVING COUNT(*) > 100
        ORDER BY cancel_rate_pct DESC
    """,

    "monthly_cohort": """
        SELECT
            TO_CHAR(DATE_TRUNC('month', order_purchase_timestamp), 'YYYY-MM') AS order_month,
            COUNT(*)                                    AS total_orders,
            COUNT(DISTINCT customer_id)                 AS unique_customers,
            ROUND(SUM(order_revenue)::NUMERIC, 2)      AS monthly_gmv,
            ROUND(AVG(order_revenue)::NUMERIC, 2)      AS avg_order_value
        FROM fact_orders
        WHERE order_purchase_timestamp IS NOT NULL
          AND order_status = 'delivered'
        GROUP BY DATE_TRUNC('month', order_purchase_timestamp)
        ORDER BY DATE_TRUNC('month', order_purchase_timestamp)
    """,

    "delivery_delay_by_state": """
        SELECT
            s.seller_state,
            COUNT(*)                                           AS total_orders,
            ROUND(AVG(f.delivery_delay_days)::NUMERIC, 2)    AS avg_delay_days,
            ROUND(MAX(f.delivery_delay_days)::NUMERIC, 2)    AS worst_delay_days,
            COUNT(*) FILTER (WHERE f.delivery_delay_days > 0) AS late_deliveries,
            ROUND(COUNT(*) FILTER (WHERE f.delivery_delay_days > 0)
                  * 100.0 / COUNT(*), 2)                     AS late_pct
        FROM fact_orders f
        JOIN dim_sellers s USING (seller_id)
        WHERE f.order_status = 'delivered'
          AND f.delivery_delay_days IS NOT NULL
        GROUP BY s.seller_state
        HAVING COUNT(*) > 100
        ORDER BY late_pct DESC
    """
}

os.makedirs("data/processed", exist_ok=True)

for name, sql in queries.items():
    df = pd.read_sql(text(sql), engine)
    path = f"data/processed/{name}.csv"
    df.to_csv(path, index=False)
    print(f"Exported {name}.csv — {len(df)} rows")

print("\nAll exports complete.")
