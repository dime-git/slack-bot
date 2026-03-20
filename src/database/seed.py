"""Generate realistic sample data for the Rounds app portfolio."""

import random
from datetime import date

from src.database.connection import get_connection
from src.database.schema import create_tables

# Seed for reproducibility
random.seed(42)

# Apps with their platform availability and base metrics
# (app_name, platforms, base_installs, base_iap_revenue, base_ads_revenue, base_ua_cost, trend)
# trend: "growing", "declining", "stable"
APPS = [
    ("Screen Mirroring", ["Android", "iOS"], 45000, 8500, 12000, 15000, "growing"),
    ("QR Scanner", ["Android", "iOS"], 80000, 3000, 18000, 10000, "stable"),
    ("Flashlight Pro", ["Android"], 120000, 1500, 25000, 8000, "declining"),
    ("Plant Identifier", ["Android", "iOS"], 35000, 15000, 7000, 20000, "growing"),
    ("Sticker Maker", ["Android", "iOS"], 55000, 12000, 9000, 14000, "stable"),
    ("Countdown Timer", ["iOS"], 20000, 5000, 4000, 6000, "stable"),
    ("Photo Editor", ["Android", "iOS"], 90000, 20000, 22000, 25000, "growing"),
    ("Compass", ["Android"], 30000, 1000, 8000, 4000, "declining"),
    ("Sound Meter", ["Android", "iOS"], 25000, 3500, 6000, 7000, "stable"),
    ("PDF Scanner", ["Android", "iOS"], 60000, 18000, 10000, 18000, "growing"),
    ("Translator", ["Android", "iOS"], 40000, 9000, 11000, 12000, "stable"),
    ("Battery Saver", ["Android"], 70000, 2000, 16000, 9000, "declining"),
]

# Country multipliers (simulate different market sizes)
COUNTRIES = {
    "US": 1.0,
    "UK": 0.35,
    "DE": 0.30,
    "BR": 0.45,
    "IN": 0.60,
    "JP": 0.25,
    "FR": 0.22,
    "CA": 0.18,
    "AU": 0.15,
    "MX": 0.28,
    "KR": 0.20,
    "IT": 0.17,
}

# Date range: Jan 2024 - Mar 2025 (15 months, first of each month)
START_DATE = date(2024, 1, 1)
MONTHS = 15


def _generate_dates() -> list[date]:
    dates = []
    current = START_DATE
    for _ in range(MONTHS):
        dates.append(current)
        # Move to first of next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return dates


def _apply_trend(base: float, month_index: int, trend: str) -> float:
    """Apply growth/decline trend based on month index."""
    if trend == "growing":
        return base * (1 + 0.04 * month_index)
    elif trend == "declining":
        return base * (1 - 0.025 * month_index)
    return base


def _seasonal_multiplier(d: date) -> float:
    """December gets a holiday bump, summer slight dip."""
    if d.month == 12:
        return 1.35
    if d.month == 11:
        return 1.15
    if d.month in (6, 7):
        return 0.90
    return 1.0


def seed_database() -> None:
    conn = get_connection()

    # Check if data already exists (idempotent)
    cursor = conn.execute("SELECT COUNT(*) FROM app_analytics")
    if cursor.fetchone()[0] > 0:
        return

    dates = _generate_dates()
    rows = []

    for app_name, platforms, base_inst, base_iap, base_ads, base_ua, trend in APPS:
        for platform in platforms:
            # iOS generally has higher revenue per user but fewer installs
            platform_inst_mult = 0.6 if platform == "iOS" else 1.0
            platform_rev_mult = 1.4 if platform == "iOS" else 1.0

            for month_idx, d in enumerate(dates):
                seasonal = _seasonal_multiplier(d)

                for country, country_mult in COUNTRIES.items():
                    installs = int(
                        _apply_trend(base_inst, month_idx, trend)
                        * country_mult
                        * platform_inst_mult
                        * seasonal
                        * random.gauss(1.0, 0.12)
                    )
                    installs = max(0, installs)

                    iap_revenue = round(
                        _apply_trend(base_iap, month_idx, trend)
                        * country_mult
                        * platform_rev_mult
                        * seasonal
                        * random.gauss(1.0, 0.15),
                        2,
                    )
                    iap_revenue = max(0, iap_revenue)

                    ads_revenue = round(
                        _apply_trend(base_ads, month_idx, trend)
                        * country_mult
                        * seasonal
                        * random.gauss(1.0, 0.10),
                        2,
                    )
                    ads_revenue = max(0, ads_revenue)

                    ua_cost = round(
                        _apply_trend(base_ua, month_idx, trend)
                        * country_mult
                        * seasonal
                        * random.gauss(1.0, 0.08),
                        2,
                    )
                    ua_cost = max(0, ua_cost)

                    rows.append(
                        (app_name, platform, d.isoformat(), country,
                         installs, iap_revenue, ads_revenue, ua_cost)
                    )

    conn.executemany(
        """INSERT INTO app_analytics
           (app_name, platform, date, country, installs, in_app_revenue, ads_revenue, ua_cost)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    print(f"Seeded {len(rows)} rows into app_analytics.")


if __name__ == "__main__":
    create_tables()
    seed_database()
