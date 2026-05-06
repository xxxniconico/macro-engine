"""World Bank API — 中美长期宏观经济数据。

提供 1960 年至今的 GDP 增速、通胀、失业率等数据，
补上 Dalio 框架最关键的时间深度缺口。

指标：
  NY.GDP.MKTP.KD.ZG  — GDP 增速 (年%)
  FP.CPI.TOTL.ZG      — CPI 通胀 (年%)
  SL.UEM.TOTL.ZS      — 失业率 (%)
  GC.DOD.TOTL.GD.ZS   — 中央政府债务/GDP
"""

import subprocess, sqlite3, json
from datetime import date, timedelta
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/macro.db")
today = date.today().isoformat()

# 指标映射
INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "gdp_growth",
    "FP.CPI.TOTL.ZG": "cpi",
    "SL.UEM.TOTL.ZS": "unemployment",
    "GC.DOD.TOTL.GD.ZS": "govt_debt_gdp",
}

COUNTRIES = {"CN": "china", "US": "us"}


def fetch_wb(country: str, indicator: str, per_page: int = 20) -> list:
    """从 World Bank API 获取数据。"""
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page={per_page}"
    cmd = ["curl", "-s", "--max-time", "10", url]
    r = subprocess.run(cmd, capture_output=True, timeout=12)
    data = json.loads(r.stdout)
    
    if len(data) < 2 or data[1] is None:
        return []
    
    result = []
    for row in data[1]:
        if row.get("value") is not None:
            result.append({
                "date": row["date"],
                "value": row["value"]
            })
    return result


def save(name, value, date_str, src="worldbank"):
    conn = sqlite3.connect(str(DB))
    conn.execute("""
        INSERT INTO macro_indicators(indicator_name,value,date,source,confidence)
        VALUES(?,?,?,?,0.85)
        ON CONFLICT(indicator_name,date,source) DO UPDATE SET value=excluded.value
    """, (name, value, date_str, src))
    conn.commit(); conn.close()


def main():
    saved = 0
    
    for country_code, prefix in COUNTRIES.items():
        print(f"\n[{country_code}] {prefix}...")
        for wb_code, short_name in INDICATORS.items():
            indicator_name = f"{prefix}_{short_name}"
            print(f"  {indicator_name}...", end=" ")
            try:
                rows = fetch_wb(country_code, wb_code, per_page=30)
                for row in rows:
                    # WB 返回的是年度数据，用 12-31 作为日期
                    date_str = f"{row['date']}-12-31"
                    save(indicator_name, row["value"], date_str)
                saved += len(rows)
                print(f"✓ {len(rows)} records (latest: {rows[0]['date']}={rows[0]['value']})")
            except Exception as e:
                print(f"✗ {e}")
    
    print(f"\n✅ World Bank saved={saved} records")


if __name__ == "__main__":
    main()
