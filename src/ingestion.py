"""
ETL Pipeline: Load Olist CSVs → Clean → Load into PostgreSQL star schema.
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Config

load_dotenv()

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

RAW = "data/raw"

# Load CSVs 

def load_raw():
    print("Loading raw CSVs...")
    customers = pd.read_csv(f"{RAW}/olist_customers_dataset.csv")
    orders = pd.read_csv(f"{RAW}/olist_orders_dataset.csv")
    order_items = pd.read_csv(f"{RAW}/olist_order_items_dataset.csv")
    payments = pd.read_csv(f"{RAW}/olist_order_payments_dataset.csv")
    reviews = pd.read_csv(f"{RAW}/olist_order_reviews_dataset.csv")
    products = pd.read_csv(f"{RAW}/olist_products_dataset.csv")
    sellers = pd.read_csv(f"{RAW}/olist_sellers_dataset.csv")
    translation = pd.read_csv(f"{RAW}/product_category_name_translation.csv")
    print(f"orders: {len(orders):,} rows")
    print(f"customers: {len(customers):,} rows")
    print(f"order_items: {len(order_items):,} rows")
    print(f"payments: {len(payments):,} rows")
    print(f"products: {len(products):,} rows")
    return customers, orders, order_items, payments, reviews, products, sellers, translation


# Build dim_customers

def build_dim_customers(customers):
    print("\nBuilding dim_customers...")
    dim = customers[[
        "customer_id",
        "customer_unique_id",
        "customer_city",
        "customer_state"
    ]].drop_duplicates(subset="customer_id")
    print(f"  Rows: {len(dim):,}")
    return dim


# Build dim_products 

def build_dim_products(products, translation):
    print("\nBuilding dim_products...")
    dim = products.merge(translation, on="product_category_name", how="left")
    dim = dim[[
        "product_id",
        "product_category_name",
        "product_category_name_english",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm"
    ]].drop_duplicates(subset="product_id")
    dim.rename(columns={"product_category_name_english": "product_category_en"}, inplace=True)
    print(f"  Rows: {len(dim):,}")
    return dim


# Build dim_sellers

def build_dim_sellers(sellers):
    print("\nBuilding dim_sellers...")
    dim = sellers[[
        "seller_id",
        "seller_city",
        "seller_state"
    ]].drop_duplicates(subset="seller_id")
    print(f"Rows: {len(dim):,}")
    return dim


# Build dim_payments

def build_dim_payments(payments):
    print("\nBuilding dim_payments...")
    # Multiple payment rows per order → aggregate to one row per order
    # Take dominant payment type (most common per order), sum value
    payment_type = (
        payments.groupby("order_id")["payment_type"]
        .agg(lambda x: x.value_counts().index[0])   # most frequent type
        .reset_index()
    )
    payment_agg = payments.groupby("order_id").agg(
        payment_installments=("payment_installments", "max"),
        payment_value=("payment_value", "sum")
    ).reset_index()
    dim = payment_type.merge(payment_agg, on="order_id")
    print(f"Rows: {len(dim):,}")
    return dim


# Build fact_orders

def build_fact_orders(orders, order_items, reviews):
    print("\nBuilding fact_orders...")

    # Timestamp columns to parse
    ts_cols = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ]
    for col in ts_cols:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    # Keep one item row per order (take first item — order-level granularity)
    # For multi-item orders, price = sum of all items
    items_agg = order_items.groupby("order_id").agg(
        product_id=("product_id", "first"),
        seller_id=("seller_id", "first"),
        price=("price", "sum"),
        freight_value=("freight_value", "sum")
    ).reset_index()

    # Aggregate reviews to one score per order
    review_agg = (
        reviews.groupby("order_id")["review_score"]
        .mean()
        .round(0)
        .astype("Int64")
        .reset_index()
    )

    # Merge all
    fact = orders.merge(items_agg, on="order_id", how="left")
    fact = fact.merge(review_agg, on="order_id", how="left")

    # Derived columns
    fact["order_revenue"] = fact["price"] + fact["freight_value"]
    fact["purchase_year"] = fact["order_purchase_timestamp"].dt.year
    fact["purchase_month"] = fact["order_purchase_timestamp"].dt.month
    fact["purchase_day_of_week"] = fact["order_purchase_timestamp"].dt.dayofweek
    fact["delivery_delay_days"] = (
        fact["order_delivered_customer_date"] - fact["order_estimated_delivery_date"]
    ).dt.days

    # Select final columns
    fact = fact[[
        "order_id", "customer_id", "product_id", "seller_id",
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date", "order_status",
        "price", "freight_value", "order_revenue",
        "purchase_year", "purchase_month", "purchase_day_of_week",
        "delivery_delay_days", "review_score"
    ]]

    print(f"Rows: {len(fact):,}")
    print(f"Null product_id: {fact['product_id'].isna().sum():,}")
    print(f"Null customer_id: {fact['customer_id'].isna().sum():,}")
    return fact


# Write to PostgreSQL

def write_to_db(engine, dim_customers, dim_products, dim_sellers, dim_payments, fact_orders):
    print("\nWriting to PostgreSQL...")

    # Load dimensions first (fact has foreign keys to them)
    dim_customers.to_sql("dim_customers", engine, if_exists="append", index=False)
    print("dim_customers loaded")

    dim_products.to_sql("dim_products", engine, if_exists="append", index=False)
    print("dim_products loaded")

    dim_sellers.to_sql("dim_sellers", engine, if_exists="append", index=False)
    print("dim_sellers loaded")

    dim_payments.to_sql("dim_payments", engine, if_exists="append", index=False)
    print("dim_payments loaded")

    # Drop fact rows where FK references don't exist (data quality)
    valid_customers = set(dim_customers["customer_id"])
    valid_products = set(dim_products["product_id"])
    valid_sellers = set(dim_sellers["seller_id"])

    before = len(fact_orders)
    fact_orders = fact_orders[
        fact_orders["customer_id"].isin(valid_customers) &
        (fact_orders["product_id"].isin(valid_products) | fact_orders["product_id"].isna()) &
        (fact_orders["seller_id"].isin(valid_sellers) | fact_orders["seller_id"].isna())
    ]
    dropped = before - len(fact_orders)
    if dropped > 0:
        print(f"Dropped {dropped:,} fact rows with missing FK references")

    fact_orders.to_sql("fact_orders", engine, if_exists="append", index=False)
    print(f"fact_orders loaded — {len(fact_orders):,} rows")


# Main

if __name__ == "__main__":
    engine = create_engine(DB_URL)

    customers, orders, order_items, payments, reviews, products, sellers, translation = load_raw()

    dim_customers = build_dim_customers(customers)
    dim_products  = build_dim_products(products, translation)
    dim_sellers   = build_dim_sellers(sellers)
    dim_payments  = build_dim_payments(payments)
    fact_orders   = build_fact_orders(orders, order_items, reviews)

    write_to_db(engine, dim_customers, dim_products, dim_sellers, dim_payments, fact_orders)

    print("\nIngestion complete.")