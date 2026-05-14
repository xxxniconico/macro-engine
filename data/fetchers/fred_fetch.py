#!/usr/bin/env python3
"""
FRED API Fetcher — replaces World Bank annual data with high-frequency US macro.

Fetches 11 key FRED series and inserts into macro.db.
Handles CPI YoY transformation (FRED gives index level, engine expects %).
Resamples daily series to monthly averages to keep DB volume manageable.

Series mapping:
  CPIAUCSL     → us_cpi            (monthly YoY%, computed from index)
  UNRATE       → us_unemployment   (monthly %)
  DFF          → us_fed_rate       (daily → monthly avg)
  T10Y2Y       → us_yield_curve    (daily → monthly avg, real 10Y-2Y spread)
  A191RL1Q225SBEA → us_gdp_growth  (quarterly % SAAR)
  GFDEGDQ188S  → us_govt_debt_gdp  (quarterly %)
  VIXCLS       → us_vix            (daily → monthly avg, NEW indicator)
  M2SL         → us_m2             (monthly billions USD, NEW)
  DGS10        → us_10y_treasury   (daily → monthly avg, NEW)
  DGS2         → us_2y_treasury    (daily → monthly avg, NEW)
  DTWEXBGS     → us_dollar_index   (daily → monthly avg, NEW)

Usage:
  python data/fetchers/fred_fetch.py           # Fetch all series
  python data/fetchers/fred_fetch.py --dry-run  # Print without inserting
"""

import os
import sys
import json
import sqlite3
import urllib.request
from datetime import datetime, timedelta

API_KEY = os.environ.get("FRED_API_KEY", "6dabf85bf516a71b9948849960fe18f7")
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Series config: (series_id, indicator_name, freq, transform)
# transform: None=direct, "yoy"=CPI YoY%, "monthly_avg"=resample daily→monthly
SERIES_CONFIG = [
    # --- UPGRADED existing indicators ---
    ("CPIAUCSL",        "us_cpi",           "monthly",  "yoy"),
    ("UNRATE",          "us_unemployment",  "monthly",  None),
    ("DFF",             "us_fed_rate",      "daily",    "monthly_avg"),
    ("T10Y2Y",          "us_yield_curve",   "daily",    "monthly_avg"),
    ("A191RL1Q225SBEA", "us_gdp_growth",    "quarterly", None),
    ("GFDEGDQ188S",     "us_govt_debt_gdp", "quarterly", None),
    # --- NEW indicators ---
    ("VIXCLS",          "us_vix",           "daily",    "monthly_avg"),
    ("M2SL",            "us_m2",            "monthly",  None),
    ("DGS10",           "us_10y_treasury",  "daily",    "monthly_avg"),
    ("DGS2",            "us_2y_treasury",   "daily",    "monthly_avg"),
    ("DTWEXBGS",        "us_dollar_index",  "daily",    "monthly_avg"),
]


def fetch_series(series_id, limit=50000):
    """Fetch all observations for a FRED series. Returns list of {date, value}."""
    url = f"{BASE_URL}?series_id={series_id}&api_key={API_KEY}&file_type=json&limit={limit}&sort_order=asc"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if "observations" not in data:
        print(f"  ⚠ {series_id}: no observations (error: {data})", file=sys.stderr)
        return []
    return [
        {"date": obs["date"], "value": float(obs["value"])}
        for obs in data["observations"]
        if obs["value"] != "." and obs["value"] is not None
    ]


def to_monthly_avg(daily_data):
    """Resample daily observations to monthly averages."""
    from collections import defaultdict
    monthly = defaultdict(list)
    for obs in daily_data:
        month_key = obs["date"][:7]  # "YYYY-MM"
        monthly[month_key].append(obs["value"])
    result = []
    for month_key in sorted(monthly):
        avg = sum(monthly[month_key]) / len(monthly[month_key])
        result.append({"date": f"{month_key}-01", "value": round(avg, 2)})
    return result


def compute_cpi_yoy(cpi_data):
    """Compute YoY% change from CPI index levels. Returns [{date, value:%}]."""
    result = []
    values_by_month = {}
    for obs in cpi_data:
        values_by_month[obs["date"]] = obs["value"]
    
    for obs in cpi_data:
        # Find same month 1 year ago
        year, month = int(obs["date"][:4]), int(obs["date"][5:7])
        prev_date = f"{year-1:04d}-{month:02d}-01"
        if prev_date in values_by_month and values_by_month[prev_date] > 0:
            yoy = (obs["value"] - values_by_month[prev_date]) / values_by_month[prev_date] * 100
            result.append({"date": obs["date"], "value": round(yoy, 2)})
    
    return result


def save_to_db(db_path, indicator_name, observations, dry_run=False):
    """Insert observations into macro.db with ON CONFLICT DO UPDATE."""
    if not observations:
        return 0
    
    if dry_run:
        print(f"  [DRY-RUN] {indicator_name}: {len(observations)} pts, "
              f"{observations[0]['date']} → {observations[-1]['date']}")
        return len(observations)
    
    db = sqlite3.connect(db_path)
    source = "fred_api"
    inserted = 0
    for obs in observations:
        try:
            db.execute(
                """INSERT INTO macro_indicators(indicator_name, value, date, source, confidence)
                   VALUES(?, ?, ?, ?, 0.97)
                   ON CONFLICT(indicator_name, date, source) DO UPDATE SET value=excluded.value""",
                (indicator_name, obs["value"], obs["date"], source)
            )
            inserted += 1
        except Exception as e:
            print(f"  ⚠ {indicator_name} {obs['date']}: {e}", file=sys.stderr)
    
    db.commit()
    db.close()
    return inserted


def main():
    dry_run = "--dry-run" in sys.argv
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "macro.db")
    db_path = os.path.abspath(db_path)
    
    if not os.path.exists(db_path):
        print(f"❌ macro.db not found at {db_path}", file=sys.stderr)
        sys.exit(1)
    
    total = 0
    for series_id, indicator_name, freq, transform in SERIES_CONFIG:
        print(f"📡 {series_id} → {indicator_name} ...", end=" ", flush=True)
        try:
            raw = fetch_series(series_id)
            if not raw:
                print(f"empty")
                continue
            
            # Apply transformation
            if transform == "yoy":
                observations = compute_cpi_yoy(raw)
            elif transform == "monthly_avg":
                observations = to_monthly_avg(raw)
            else:
                observations = raw
            
            n = save_to_db(db_path, indicator_name, observations, dry_run)
            print(f"{len(raw)} raw → {n} saved  ({observations[0]['date']} → {observations[-1]['date']})")
            total += n
        except Exception as e:
            print(f"❌ {e}")
    
    action = "Would insert" if dry_run else "Inserted"
    print(f"\n✅ {action} {total} records across {len(SERIES_CONFIG)} indicators")


if __name__ == "__main__":
    main()
