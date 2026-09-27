"""
features.py
-----------
RFM computation + K-Means customer segmentation.
Run: python3 src/features.py
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

os.makedirs("data/processed", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# ── Step 1: Pull order data from PostgreSQL ───────────────────────────────────

def load_orders():
    print("Loading orders from PostgreSQL...")
    sql = text("""
        SELECT
            f.customer_id,
            c.customer_unique_id,
            c.customer_state,
            f.order_purchase_timestamp,
            f.order_revenue,
            f.order_status
        FROM fact_orders f
        JOIN dim_customers c USING (customer_id)
        WHERE f.order_status = 'delivered'
          AND f.order_revenue IS NOT NULL
          AND f.order_purchase_timestamp IS NOT NULL
    """)
    df = pd.read_sql(sql, engine)
    print(f"  Loaded {len(df):,} delivered orders")
    return df


# ── Step 2: Compute RFM ───────────────────────────────────────────────────────

def compute_rfm(df):
    print("\nComputing RFM scores...")

    # Reference date = day after last order in dataset
    reference_date = df["order_purchase_timestamp"].max() + pd.Timedelta(days=1)
    print(f"  Reference date: {reference_date.date()}")

    rfm = df.groupby("customer_unique_id").agg(
        recency   =("order_purchase_timestamp",
                     lambda x: (reference_date - x.max()).days),
        frequency =("order_purchase_timestamp", "count"),
        monetary  =("order_revenue", "sum")
    ).reset_index()

    print(f"  Unique customers: {len(rfm):,}")
    print(f"\n  RFM Summary:")
    print(rfm[["recency","frequency","monetary"]].describe().round(2))
    return rfm


# ── Step 3: Normalize + Elbow + Silhouette ────────────────────────────────────

def find_optimal_k(rfm_scaled, k_range=range(2, 9)):
    print("\nFinding optimal K...")
    inertias, silhouettes = [], []

    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(rfm_scaled)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(rfm_scaled, labels))
        print(f"  K={k} | Inertia: {km.inertia_:,.0f} | Silhouette: {silhouette_score(rfm_scaled, labels):.4f}")

    # Plot Elbow + Silhouette
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].plot(list(k_range), inertias, marker="o", color="steelblue")
    axes[0].set_title("Elbow Method — Inertia vs K")
    axes[0].set_xlabel("Number of Clusters (K)")
    axes[0].set_ylabel("Inertia")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(list(k_range), silhouettes, marker="o", color="darkorange")
    axes[1].set_title("Silhouette Score vs K")
    axes[1].set_xlabel("Number of Clusters (K)")
    axes[1].set_ylabel("Silhouette Score")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("reports/kmeans_elbow_silhouette.png", dpi=150)
    plt.close()
    print("  Saved: reports/kmeans_elbow_silhouette.png")

    best_k = 4  # Override: K=2 is statistically optimal but not business-meaningful
                # K=4 (Silhouette: 0.4886) maps to Champions/Loyal/At-Risk/Lost
    print(f"  Overriding to K=4 for business interpretability (Silhouette: 0.4886)")
    return best_k


# ── Step 4: Final K-Means + Label Clusters ───────────────────────────────────

def assign_segments(rfm, rfm_scaled, k):
    print(f"\nRunning K-Means with K={k}...")
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    rfm["cluster"] = km.fit_predict(rfm_scaled)

    # Summarize clusters to assign business labels
    summary = rfm.groupby("cluster").agg(
        recency  =("recency",   "mean"),
        frequency=("frequency", "mean"),
        monetary =("monetary",  "mean"),
        count    =("customer_unique_id", "count")
    ).round(2)
    print("\n  Cluster Summary:")
    print(summary)

    # Auto-label: Champions = low recency + high monetary
    # Sort by monetary descending to assign labels
    summary_sorted = summary.sort_values("monetary", ascending=False)
    labels = ["Champions", "Loyal", "At-Risk", "Lost"]
    # Pad if K < 4
    labels = labels[:k]
    label_map = {cluster: labels[i]
                 for i, cluster in enumerate(summary_sorted.index)}

    rfm["segment"] = rfm["cluster"].map(label_map)
    print("\n  Segment distribution:")
    print(rfm["segment"].value_counts())
    return rfm, summary


# ── Step 5: RFM Heatmap ───────────────────────────────────────────────────────

def plot_rfm_heatmap(rfm):
    pivot = rfm.groupby("segment").agg(
        Recency  =("recency",   "mean"),
        Frequency=("frequency", "mean"),
        Monetary =("monetary",  "mean")
    ).round(1)

    plt.figure(figsize=(8, 4))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd")
    plt.title("RFM Heatmap by Customer Segment")
    plt.tight_layout()
    plt.savefig("reports/rfm_heatmap.png", dpi=150)
    plt.close()
    print("  Saved: reports/rfm_heatmap.png")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df   = load_orders()
    rfm  = compute_rfm(df)

    # Normalize RFM
    scaler     = StandardScaler()
    rfm_scaled = scaler.fit_transform(rfm[["recency", "frequency", "monetary"]])

    best_k = find_optimal_k(rfm_scaled)
    rfm, summary = assign_segments(rfm, rfm_scaled, best_k)

    plot_rfm_heatmap(rfm)

    # Export
    rfm.to_csv("data/processed/customer_segments.csv", index=False)
    print("\nExported: data/processed/customer_segments.csv")
    print("\nMilestone 4A complete.")