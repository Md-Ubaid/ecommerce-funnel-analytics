# E-Commerce Funnel Leakage & Revenue Recovery Engine
 
> End-to-end data analytics pipeline on 100K+ real orders — identifying funnel drop-off, predicting customer churn, and surfacing revenue-at-risk via an executive Power BI dashboard.
 
![Status](https://img.shields.io/badge/Status-In%20Progress-yellow)
![Python](https://img.shields.io/badge/Python-3.14-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.6-336791?logo=postgresql)
![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-F2C811?logo=powerbi)
 
---
 
## Business Problem
 
Typical e-commerce platforms lose 95–97% of visitors before checkout. This project answers:
- **Where** exactly does revenue bleed out across the buying funnel?
- **Which customers** are likely to churn in the next 90 days?
- **How much GMV** is at risk daily — and which segments drive it?
---
 
## Project Architecture
 
```
Raw CSVs (Olist, 8 files)
        │
        ▼
  Python ETL Pipeline
  (pandas → cleaning → merging)
        │
        ▼
  PostgreSQL Star Schema
  (fact_orders + 4 dim tables)
        │
        ├──────────────────────┐
        ▼                      ▼
  SQL Funnel Analysis     Python ML Pipeline
  (window functions,      (RFM → K-Means,
   cohort retention)       XGBoost churn model)
        │                      │
        └──────────┬───────────┘
                   ▼
         Power BI Executive Dashboard
         (Funnel · Segments · Churn · Revenue-at-Risk)
```
 
---
 
## Dataset
 
**Source:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — Kaggle
 
| File | Description |
|---|---|
| `olist_orders_dataset.csv` | Core order lifecycle + status |
| `olist_customers_dataset.csv` | Customer ID, city, state |
| `olist_order_items_dataset.csv` | SKU-level price, freight, seller |
| `olist_products_dataset.csv` | Product category, dimensions |
| `olist_sellers_dataset.csv` | Seller location |
| `olist_order_payments_dataset.csv` | Payment method, installments, value |
| `olist_order_reviews_dataset.csv` | Review score, comment |
| `olist_geolocation_dataset.csv` | Zip-code lat/lon mapping |
 
> **Note:** Raw data files are excluded from this repo (`.gitignore`). Download directly from Kaggle and place under `data/raw/`.
 
---
 
## Tech Stack
 
| Layer | Tools |
|---|---|
| Data Manipulation | Python 3.14, pandas, NumPy |
| Database | PostgreSQL 18.6, SQLAlchemy, psycopg2 |
| Machine Learning | scikit-learn, XGBoost, imbalanced-learn |
| Visualization | matplotlib, seaborn |
| BI Dashboard | Power BI Desktop |
| Environment | virtualenv, python-dotenv, JupyterLab |
| Version Control | Git, GitHub |
 
---
 
## Repository Structure
 
```
ecommerce-funnel-analytics/
│
├── data/
│   ├── raw/              # Original Olist CSVs (not committed)
│   └── processed/        # Cleaned outputs
│
├── database/
│   └── schema.sql        # Star schema DDL
│
├── notebooks/
│   └── 01_eda.ipynb      # Exploratory analysis
│
├── src/
│   ├── ingestion.py      # ETL: load CSVs → PostgreSQL
│   ├── cleaning.py       # Null handling, date parsing, deduplication
│   ├── features.py       # RFM computation, feature engineering
│   └── model.py          # K-Means segmentation + XGBoost pipeline
│
├── dashboards/
│   └── funnel_dashboard.pbix
│
├── reports/
│   └── architecture.png
│
├── .env                  # DB credentials (not committed)
├── .gitignore
├── requirements.txt
└── README.md
```
 
---
 
## Local Setup
 
### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/ecommerce-funnel-analytics.git
cd ecommerce-funnel-analytics
```
 
### 2. Create & Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```
 
### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
 
### 4. Configure Environment Variables
```bash
cp .env.example .env   # then fill in your credentials
```
 
`.env` structure:
```
DB_USER=olist_user
DB_PASSWORD=olist_pass
DB_HOST=localhost
DB_PORT=5432
DB_NAME=olist_db
```
 
### 5. Set Up PostgreSQL
```bash
sudo -u postgres psql
```
```sql
CREATE USER olist_user WITH PASSWORD 'olist_pass';
CREATE DATABASE olist_db OWNER olist_user;
GRANT ALL PRIVILEGES ON DATABASE olist_db TO olist_user;
\q
```
 
### 6. Download Dataset
Download from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and place all CSVs in `data/raw/`.
 
---
 
## Milestones
 
| # | Milestone | Status |
|---|---|---|
| 1 | GitHub repo, virtual environment, PostgreSQL setup | ✅ Complete |
| 2 | Data ingestion — ETL pipeline, star schema | 🔄 In Progress |
| 3 | SQL funnel analysis — window functions, cohort retention | ⏳ Pending |
| 4 | ML pipeline — RFM/K-Means segmentation + XGBoost churn model | ⏳ Pending |
| 5 | Power BI executive dashboard | ⏳ Pending |
| 6 | Documentation, architecture diagram, resume bullets | ⏳ Pending |
 
---
 
## Results (Updated After Each Milestone)
 
| Metric | Value |
|---|---|
| Dataset size | 100K+ orders |
| Funnel drop-off identified | TBD |
| Churn model ROC-AUC | TBD |
| K-Means clusters (K) | TBD |
| Daily GMV at risk | TBD |
 
---
 
## Resume Bullet (Template — Fill With Actual Metrics)
 
> *"Built an end-to-end e-commerce analytics pipeline on 100K+ Olist orders using Python, SQL, and Power BI — segmented customers into N RFM clusters via K-Means (Silhouette: 0.XX), predicted 90-day churn with XGBoost (ROC-AUC: 0.XX), and quantified ₹X revenue-at-risk daily on an executive Power BI dashboard with drill-through capability."*
 
---
 
## Author
 
**Ubaid** — 3rd-year B.Tech Student | Aspiring Data Analyst / Data Scientist
 
[![GitHub](https://img.shields.io/badge/GitHub-Portfolio-black?logo=github)](https://github.com/YOUR_USERNAME)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://linkedin.com/in/YOUR_PROFILE)