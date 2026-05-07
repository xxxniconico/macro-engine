#!/usr/bin/env python3
"""Phase 3: JST Macrohistory Database — 百年尺度数据 (1870-2020)
Jordà-Schularick-Taylor Macrohistory Database R6
18 advanced economies, 59 variables, 150 years

Key additions for Dalio long-term debt cycle framework:
  - US real GDP growth, inflation, interest rates → 150yr secular trends
  - US debt/GDP supercycle → full 3 long-term debt cycle history
  - US equity/housing/bond total returns → asset class century returns
  - G7 composite → cross-country cycle comparison
"""
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).parent.parent.parent
DB = PROJECT / "macro.db"
JST_DTA = Path("/tmp/JSTdatasetR6.dta")

# G7 country ISO codes (US, UK, Germany, France, Japan, Italy, Canada)
G7_ISO = {"USA", "GBR", "DEU", "FRA", "JPN", "ITA", "CAN"}


def load_jst():
    """Load JST dataset from Stata file."""
    if not JST_DTA.exists():
        print("  ⚠ JST dataset not found at", JST_DTA)
        print("    Download from: https://www.macrohistory.net/database/")
        return None
    return pd.read_stata(str(JST_DTA))


def extract_us_series(df):
    """Extract US time series from JST, returning {indicator_name: {date: value}}."""
    us = df[df["iso"] == "USA"].copy()
    if us.empty:
        return {}

    result = {}

    # --- Real GDP growth (YoY, computed from real GDP index) ---
    us = us.sort_values("year")
    us["rgdp_growth"] = us["rgdpmad"].pct_change() * 100
    gdp_growth = {}
    for _, row in us.iterrows():
        if not np.isnan(row["rgdp_growth"]):
            gdp_growth[f"{int(row['year'])}-12-31"] = round(row["rgdp_growth"], 2)
    if gdp_growth:
        result["us_rgdp_growth_lt"] = gdp_growth

    # --- CPI inflation (YoY from CPI level) ---
    us["inflation"] = us["cpi"].pct_change() * 100
    inflation = {}
    for _, row in us.iterrows():
        if not np.isnan(row["inflation"]):
            inflation[f"{int(row['year'])}-12-31"] = round(row["inflation"], 2)
    if inflation:
        result["us_inflation_lt"] = inflation

    # --- Short-term interest rate ---
    stir = {}
    for _, row in us.iterrows():
        if not np.isnan(row["stir"]):
            stir[f"{int(row['year'])}-12-31"] = round(row["stir"], 2)
    if stir:
        result["us_stir_lt"] = stir

    # --- Long-term interest rate ---
    ltrate = {}
    for _, row in us.iterrows():
        if not np.isnan(row["ltrate"]):
            ltrate[f"{int(row['year'])}-12-31"] = round(row["ltrate"], 2)
    if ltrate:
        result["us_ltrate_lt"] = ltrate

    # --- Real interest rate (stir - cpi inflation) ---
    us["real_rate"] = us["stir"] - us["inflation"]
    real_rate = {}
    for _, row in us.iterrows():
        if not np.isnan(row["real_rate"]):
            real_rate[f"{int(row['year'])}-12-31"] = round(row["real_rate"], 2)
    if real_rate:
        result["us_real_rate_lt"] = real_rate

    # --- Government debt / GDP ---
    debtgdp = {}
    for _, row in us.iterrows():
        if not np.isnan(row["debtgdp"]):
            debtgdp[f"{int(row['year'])}-12-31"] = round(row["debtgdp"] * 100, 1)
    if debtgdp:
        result["us_debtgdp_lt"] = debtgdp

    # --- Equity total return (annual) ---
    eq_tr = {}
    for _, row in us.iterrows():
        if not np.isnan(row["eq_tr"]):
            eq_tr[f"{int(row['year'])}-12-31"] = round(row["eq_tr"] * 100, 2)
    if eq_tr:
        result["us_eq_return_lt"] = eq_tr

    # --- Housing total return (annual) ---
    housing_tr = {}
    for _, row in us.iterrows():
        if not np.isnan(row["housing_tr"]):
            housing_tr[f"{int(row['year'])}-12-31"] = round(row["housing_tr"] * 100, 2)
    if housing_tr:
        result["us_housing_return_lt"] = housing_tr

    # --- Investment / GDP ratio ---
    iy = {}
    for _, row in us.iterrows():
        if not np.isnan(row["iy"]):
            iy[f"{int(row['year'])}-12-31"] = round(row["iy"] * 100, 1)
    if iy:
        result["us_investment_gdp_lt"] = iy

    # --- Current account / GDP ---
    ca = {}
    for _, row in us.iterrows():
        if not np.isnan(row["ca"]):
            ca[f"{int(row['year'])}-12-31"] = round(row["ca"], 1)
    if ca:
        result["us_current_account_lt"] = ca

    # --- Unemployment ---
    unemp = {}
    for _, row in us.iterrows():
        if not np.isnan(row["unemp"]):
            unemp[f"{int(row['year'])}-12-31"] = round(row["unemp"], 2)
    if unemp:
        result["us_unemployment_lt"] = unemp

    return result


def extract_g7_composites(df):
    """Compute G7 average inflation and debt/GDP."""
    g7 = df[df["iso"].isin(G7_ISO)].copy()
    g7 = g7.sort_values(["iso", "year"])

    # G7 average inflation
    g7["inflation"] = g7.groupby("iso")["cpi"].pct_change() * 100
    g7_inf = g7.groupby("year")["inflation"].mean()

    g7_inflation = {}
    for yr, val in g7_inf.items():
        if not np.isnan(val):
            g7_inflation[f"{int(yr)}-12-31"] = round(val, 2)

    # G7 average debt/GDP
    g7_debt = g7.groupby("year")["debtgdp"].mean()
    g7_debtgdp = {}
    for yr, val in g7_debt.items():
        if not np.isnan(val):
            g7_debtgdp[f"{int(yr)}-12-31"] = round(val * 100, 1)

    return {
        "g7_inflation_lt": g7_inflation,
        "g7_debtgdp_lt": g7_debtgdp,
    }


def insert_data(db_path, indicator_name, data_dict, source="jst_macrohistory"):
    """Insert data into macro_indicators. Uses INSERT OR REPLACE."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    inserted = 0
    for date_str, value in sorted(data_dict.items()):
        try:
            c.execute("""
                INSERT OR REPLACE INTO macro_indicators (indicator_name, date, value, source)
                VALUES (?, ?, ?, ?)
            """, (indicator_name, date_str, round(float(value), 2), source))
            inserted += 1
        except Exception as e:
            print(f"  DB error {indicator_name} {date_str}: {e}")
    conn.commit()
    conn.close()
    return inserted


def main():
    print("📦 Phase 3: JST Macrohistory 百年尺度数据")
    print(f"   数据库: {DB}")
    print(f"   JST源:  {JST_DTA}")
    print()

    df = load_jst()
    if df is None:
        print("❌ 无法加载 JST 数据")
        return

    us_min = int(df[df["iso"] == "USA"]["year"].min())
    us_max = int(df[df["iso"] == "USA"]["year"].max())
    print(f"   US 数据: {us_min}-{us_max} ({us_max - us_min + 1} 年)")
    print(f"   覆盖国家: {len(df['iso'].unique())} 个")
    print()

    total = 0

    # 1. US century-scale series
    print("1/2 美国百年尺度指标...")
    us_series = extract_us_series(df)
    for name, data in us_series.items():
        n = insert_data(DB, name, data)
        print(f"  ✓ {name}: {n} records ({min(data.keys())[:4]}-{max(data.keys())[:4]})")
        total += n

    # 2. G7 composites
    print("\n2/2 G7 跨国对比...")
    g7_series = extract_g7_composites(df)
    for name, data in g7_series.items():
        n = insert_data(DB, name, data)
        print(f"  ✓ {name}: {n} records")
        total += n

    print(f"\n✅ Phase 3 完成! 共写入 {total} 条记录")
    print(f"   新增指标: {len(us_series) + len(g7_series)} 个")


if __name__ == "__main__":
    main()
