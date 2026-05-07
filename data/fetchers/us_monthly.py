"""
美国月度宏观数据抓取 — 填补当前 seed/manual 缺口。

覆盖指标:
  us_pmi       — ISM 制造业 PMI (月度)
  us_cpi       — CPI 同比 (月度)
  us_unemployment — 失业率 (月度)

数据源:
  - 东方财富美国宏观 (eastmoney)
  - FRED API (备份, 需要 API key)
  - World Bank (年度, 已有)
"""

import sqlite3
import json
import subprocess
from datetime import date
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/macro.db")
today = date.today().isoformat()

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}


def save(name, value, src="eastmoney_us"):
    conn = sqlite3.connect(str(DB))
    conn.execute("""
        INSERT INTO macro_indicators(indicator_name,value,date,source) 
        VALUES(?,?,?,?) 
        ON CONFLICT(indicator_name,date,source) DO UPDATE SET value=excluded.value
    """, (name, value, today, src))
    conn.commit()
    conn.close()


def curl_json(url: str) -> dict:
    cmd = ["curl", "-s", "--max-time", "10", url]
    r = subprocess.run(cmd, capture_output=True, timeout=12)
    return json.loads(r.stdout)


saved = 0

# ═══ 1. 美国 ISM PMI ═══
print("[1/3] 美国 ISM PMI...")
try:
    # 东方财富 — 美国 ISM 制造业 PMI
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_US_PMI&columns=REPORT_DATE,MAKE_INDEX&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=3&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        latest = data["result"]["data"][0]
        val = latest.get("MAKE_INDEX")
        if val:
            save("us_pmi", val)
            saved += 1
            print(f"  ✓ us_pmi = {val}")
except Exception as e:
    print(f"  ⚠️ 东方财富 US PMI API 不可用: {e}")

# ═══ 2. 美国 CPI ═══
print("[2/3] 美国 CPI...")
try:
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_US_CPI&columns=REPORT_DATE,NATIONAL_SAME&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=3&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        latest = data["result"]["data"][0]
        val = latest.get("NATIONAL_SAME")
        if val:
            save("us_cpi", val)
            saved += 1
            print(f"  ✓ us_cpi = {val}%")
except Exception as e:
    print(f"  ⚠️ 东方财富 US CPI API 不可用: {e}")

# ═══ 3. 美国失业率 ═══
print("[3/3] 美国失业率...")
try:
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_US_UNEMPLOYMENT&columns=REPORT_DATE,UNEMPLOYMENT_RATE&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=3&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        latest = data["result"]["data"][0]
        val = latest.get("UNEMPLOYMENT_RATE")
        if val:
            save("us_unemployment", val)
            saved += 1
            print(f"  ✓ us_unemployment = {val}%")
except Exception as e:
    print(f"  ⚠️ 东方财富 US 失业率 API 不可用: {e}")

# ═══ 兜底：如果全部失败，从 World Bank 取年度数据 ═══
if saved == 0:
    print("\n⚠️ 东方财富美国 API 全失败，尝试 World Bank...")
    try:
        from data.fetchers.worldbank import main as wb_main
        wb_main()
    except Exception as e:
        print(f"  ✗ World Bank 也失败: {e}")

print(f"\n✅ us_monthly saved={saved}")
