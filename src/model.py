"""
model.py
--------
Churn prediction pipeline: XGBoost + Logistic Regression baseline.
Churn definition: customer_unique_id with no purchase in last 90 days
of the dataset window.
Run: python3 src/model.py
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import seaborn as sns
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, classification_report,
                             confusion_matrix, RocCurveDisplay)
from xgboost import XGBClassifier
import shap
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

os.makedirs("data/processed", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# ── Step 1: Load Data ─────────────────────────────────────────────────────────

def load_data():
    print("Loading data from PostgreSQL...")
    sql = text("""
        SELECT
            f.order_id,
            c.customer_unique_id,
            c.customer_state,
            f.order_purchase_timestamp,
            f.order_status,
            f.order_revenue,
            f.price,
            f.freight_value,
            f.review_score,
            f.delivery_delay_days,
            pay.payment_type,
            f.purchase_year,
            f.purchase_month,
            f.purchase_day_of_week,
            p.product_category_en
        FROM fact_orders f
        JOIN dim_customers c USING (customer_id)
        JOIN dim_products  p USING (product_id)
        LEFT JOIN dim_payments pay USING (order_id)
        WHERE f.order_status = 'delivered'
          AND f.order_purchase_timestamp IS NOT NULL
    """)
    df = pd.read_sql(sql, engine)
    print(f"  Loaded {len(df):,} rows")
    return df


# ── Step 2: Define Churn Label ────────────────────────────────────────────────

def define_churn(df, churn_days=90):
    print(f"\nDefining churn (no purchase in last {churn_days} days)...")

    max_date = df["order_purchase_timestamp"].max()
    churn_cutoff = max_date - pd.Timedelta(days=churn_days)
    print(f"  Dataset end: {max_date.date()}")
    print(f"  Churn cutoff: {churn_cutoff.date()}")

    # Per customer: last purchase date
    customer_last = df.groupby("customer_unique_id").agg(
        last_purchase=("order_purchase_timestamp", "max")
    ).reset_index()

    customer_last["churned"] = (
        customer_last["last_purchase"] < churn_cutoff
    ).astype(int)

    churn_rate = customer_last["churned"].mean() * 100
    print(f"  Churn rate: {churn_rate:.1f}%")
    print(f"  Churned: {customer_last['churned'].sum():,} | "
          f"Active: {(customer_last['churned']==0).sum():,}")
    return customer_last


# ── Step 3: Feature Engineering ───────────────────────────────────────────────

def build_features(df, customer_last):
    print("\nEngineering features...")

    # Aggregate per customer
    features = df.groupby("customer_unique_id").agg(
        total_orders      =("order_id",              "count"),
        total_revenue     =("order_revenue",          "sum"),
        avg_order_value   =("order_revenue",          "mean"),
        avg_review_score  =("review_score",           "mean"),
        avg_delivery_delay=("delivery_delay_days",    "mean"),
        avg_freight       =("freight_value",          "mean"),
        customer_state    =("customer_state",         "first"),
        top_category      =("product_category_en",   lambda x: x.mode()[0]
                             if not x.mode().empty else "unknown"),
        top_payment       =("payment_type",           lambda x: x.mode()[0]
                             if not x.mode().empty else "unknown"),
        purchase_month    =("purchase_month",         "mean"),
        purchase_dow      =("purchase_day_of_week",   "mean")
    ).reset_index()

    # Merge churn label
    data = features.merge(customer_last[["customer_unique_id","churned"]],
                          on="customer_unique_id")

    # Encode categoricals
    for col in ["customer_state", "top_category", "top_payment"]:
        le = LabelEncoder()
        data[col] = le.fit_transform(data[col].astype(str))

    data["avg_review_score"]   = data["avg_review_score"].fillna(3.0)
    data["avg_delivery_delay"] = data["avg_delivery_delay"].fillna(0.0)

    feature_cols = [
        "total_orders", "total_revenue", "avg_order_value",
        "avg_review_score", "avg_delivery_delay", "avg_freight",
        "customer_state", "top_category", "top_payment",
        "purchase_month", "purchase_dow"
    ]
    print(f"  Features: {len(feature_cols)} | Samples: {len(data):,}")
    return data, feature_cols


# ── Step 4: Time-Based Train/Test Split ───────────────────────────────────────

def split_data(df, data, feature_cols):
    print("\nSplitting data (time-based)...")

    # Customers who made their first purchase before 2018 → train
    first_purchase = df.groupby("customer_unique_id")["order_purchase_timestamp"].min()
    train_customers = first_purchase[first_purchase < "2018-01-01"].index
    test_customers  = first_purchase[first_purchase >= "2018-01-01"].index

    train = data[data["customer_unique_id"].isin(train_customers)]
    test  = data[data["customer_unique_id"].isin(test_customers)]

    X_train = train[feature_cols]
    y_train = train["churned"]
    X_test  = test[feature_cols]
    y_test  = test["churned"]

    print(f"  Train: {len(X_train):,} | Test: {len(X_test):,}")
    print(f"  Train churn rate: {y_train.mean()*100:.1f}%")
    print(f"  Test churn rate:  {y_test.mean()*100:.1f}%")
    return X_train, X_test, y_train, y_test, test


# ── Step 5: Train Models ──────────────────────────────────────────────────────

def train_models(X_train, X_test, y_train, y_test):
    print("\nTraining models...")

    # Baseline: Logistic Regression
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    lr_auc = roc_auc_score(y_test, lr.predict_proba(X_test)[:,1])
    print(f"  Logistic Regression ROC-AUC: {lr_auc:.4f}")

    # Primary: XGBoost
    scale_pos = (y_train == 0).sum() / (y_train == 1).sum()
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=scale_pos,
        random_state=42,
        eval_metric="auc",
        verbosity=0
    )
    xgb.fit(X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False)

    xgb_auc = roc_auc_score(y_test, xgb.predict_proba(X_test)[:,1])
    print(f"  XGBoost ROC-AUC:             {xgb_auc:.4f}")
    print(f"\n  XGBoost Classification Report:")
    print(classification_report(y_test, xgb.predict(X_test)))
    return lr, xgb, xgb_auc


# ── Step 6: ROC Curve ─────────────────────────────────────────────────────────

def plot_roc(lr, xgb, X_test, y_test):
    fig, ax = plt.subplots(figsize=(7, 5))
    RocCurveDisplay.from_estimator(lr,  X_test, y_test, ax=ax, name="Logistic Regression")
    RocCurveDisplay.from_estimator(xgb, X_test, y_test, ax=ax, name="XGBoost")
    ax.set_title("ROC Curve — Churn Prediction")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("reports/roc_curve.png", dpi=150)
    plt.close()
    print("  Saved: reports/roc_curve.png")


# ── Step 7: SHAP Explainability ───────────────────────────────────────────────

def plot_shap(xgb, X_test, feature_cols):
    print("\nComputing SHAP values...")
    explainer  = shap.TreeExplainer(xgb)
    shap_vals  = explainer.shap_values(X_test)

    # Global feature importance
    plt.figure(figsize=(8, 5))
    shap.summary_plot(shap_vals, X_test,
                      feature_names=feature_cols,
                      plot_type="bar", show=False)
    plt.title("SHAP Feature Importance — Churn Drivers")
    plt.tight_layout()
    plt.savefig("reports/shap_feature_importance.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved: reports/shap_feature_importance.png")


# ── Step 8: Export Predictions ────────────────────────────────────────────────

def export_predictions(xgb, data, feature_cols, test):
    print("\nExporting churn predictions...")
    all_X = data[feature_cols]
    data  = data.copy()
    data["churn_probability"] = xgb.predict_proba(all_X)[:,1]
    data["churn_prediction"]  = xgb.predict(all_X)

    out = data[["customer_unique_id", "total_orders", "total_revenue",
                "avg_order_value", "churn_probability", "churn_prediction",
                "churned"]]
    out.to_csv("data/processed/churn_predictions.csv", index=False)
    print(f"  Exported {len(out):,} rows → data/processed/churn_predictions.csv")

    # Top 20 at-risk customers
    top_risk = out.sort_values("churn_probability", ascending=False).head(20)
    print("\n  Top 10 churn risk customers:")
    print(top_risk[["customer_unique_id","churn_probability",
                    "total_revenue"]].head(10).to_string(index=False))


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df            = load_data()
    customer_last = define_churn(df)
    data, feature_cols = build_features(df, customer_last)
    X_train, X_test, y_train, y_test, test = split_data(df, data, feature_cols)
    lr, xgb, xgb_auc = train_models(X_train, X_test, y_train, y_test)

    plot_roc(lr, xgb, X_test, y_test)
    plot_shap(xgb, X_test, feature_cols)
    export_predictions(xgb, data, feature_cols, test)

    print(f"\nMilestone 4B complete. XGBoost ROC-AUC: {xgb_auc:.4f}")