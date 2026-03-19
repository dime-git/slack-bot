from src.database.connection import get_connection

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS app_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    platform TEXT NOT NULL CHECK(platform IN ('iOS', 'Android')),
    date DATE NOT NULL,
    country TEXT NOT NULL,
    installs INTEGER DEFAULT 0,
    in_app_revenue REAL DEFAULT 0.0,
    ads_revenue REAL DEFAULT 0.0,
    ua_cost REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_app_analytics_app_date ON app_analytics(app_name, date);
CREATE INDEX IF NOT EXISTS idx_app_analytics_platform ON app_analytics(platform);
CREATE INDEX IF NOT EXISTS idx_app_analytics_country ON app_analytics(country);
CREATE INDEX IF NOT EXISTS idx_app_analytics_date ON app_analytics(date);
"""

# Human-readable schema description for LLM context
SCHEMA_DESCRIPTION = """Table: app_analytics
Columns:
- app_name (TEXT): Name of a mobile app (e.g., "Screen Mirroring", "QR Scanner")
- platform (TEXT): "iOS" or "Android"
- date (DATE): Date of the data in YYYY-MM-DD format (monthly granularity, always first of month)
- country (TEXT): Two-letter country code (e.g., "US", "UK", "DE")
- installs (INTEGER): Number of app downloads for that month
- in_app_revenue (REAL): Revenue from in-app purchases in USD
- ads_revenue (REAL): Revenue from advertisements in USD
- ua_cost (REAL): User Acquisition Cost (marketing spend) in USD

Notes:
- Each row represents one app's metrics for one month in one country on one platform.
- Total revenue = in_app_revenue + ads_revenue
- Profit/ROAS can be derived from revenue vs ua_cost
- Some apps exist on both iOS and Android, some on only one platform.
"""


def create_tables() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA_DDL)
    conn.commit()
