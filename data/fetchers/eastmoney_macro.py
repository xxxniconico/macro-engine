"""东方财富数据中心抓取 - 真实中国宏观数据（PMI/CPI/M2）。

东方财富数据中心 API：https://data.eastmoney.com/
比 push2 行情接口提供更丰富的宏观数据。

API 模式：https://datacenter-web.eastmoney.com/api/data/v1/get
"""

import requests, sqlite3, json, subprocess
from datetime import date
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/macro.db")
today = date.today().isoformat()
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}

def save(name, value, src="eastmoney_dc"):
    conn = sqlite3.connect(str(DB))
    conn.execute("""
        INSERT INTO macro_indicators(indicator_name,value,date,source) 
        VALUES(?,?,?,?) 
        ON CONFLICT(indicator_name,date,source) DO UPDATE SET value=excluded.value
    """, (name, value, today, src))
    conn.commit(); conn.close()

def curl_json(url: str) -> dict:
    """用 curl 获取 JSON（绕过 Python requests SSL 问题）。"""
    cmd = ["curl", "-s", "--max-time", "10", url]
    r = subprocess.run(cmd, capture_output=True, timeout=12)
    return json.loads(r.stdout)

saved = 0

# ═══ 1. PMI（制造业采购经理指数）═══
print("[1/4] PMI...")
try:
    # 东方财富数据中心 - 中国制造业 PMI
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_PMI&columns=REPORT_DATE,MAKE_INDEX,NMAKE_INDEX&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=3&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        latest = data["result"]["data"][0]
        pmi_date = latest["REPORT_DATE"][:10]
        pmi_val = latest.get("MAKE_INDEX")
        if pmi_val:
            save("china_pmi", pmi_val)
            saved += 1
            print(f"  ✓ china_pmi = {pmi_val} ({pmi_date})")
except Exception as e:
    print(f"  ✗ PMI API: {e}")

# ═══ 2. CPI（居民消费价格指数）═══
print("[2/4] CPI...")
try:
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_CPI&columns=REPORT_DATE,TIME,NATIONAL_SAME&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=3&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        latest = data["result"]["data"][0]
        cpi_val = latest.get("NATIONAL_SAME")
        if cpi_val:
            save("china_cpi", cpi_val)
            saved += 1
            print(f"  ✓ china_cpi = {cpi_val}%")
except Exception as e:
    print(f"  ✗ CPI API: {e}")

# ═══ 3. M2 货币供应量 ═══
print("[3/4] M2...")
try:
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_M2&columns=REPORT_DATE,BASIC_CURRENCY,BASIC_CURRENCY_SAME&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=3&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        latest = data["result"]["data"][0]
        m2_val = latest.get("BASIC_CURRENCY_SAME")
        if m2_val:
            save("china_m2_yoy", m2_val)
            saved += 1
            print(f"  ✓ china_m2_yoy = {m2_val}%")
except Exception as e:
    print(f"  ✗ M2 API: {e}")

# ═══ 4. GDP ═══
print("[4/4] GDP...")
try:
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
           "reportName=RPT_ECONOMY_GDP&columns=REPORT_DATE,TIME,GDP_SAME&"
           "sortTypes=-1&sortColumns=REPORT_DATE&pageSize=5&pageNumber=1")
    data = curl_json(url)
    if data.get("result") and data["result"].get("data"):
        for row in data["result"]["data"]:
            if "季度" in str(row.get("TIME", "")):
                gdp_val = row.get("GDP_SAME")
                if gdp_val:
                    save("china_gdp_yoy", gdp_val)
                    saved += 1
                    print(f"  ✓ china_gdp_yoy = {gdp_val}% ({row['REPORT_DATE'][:10]})")
                    break
except Exception as e:
    print(f"  ✗ GDP API: {e}")

print(f"\n✅ eastmoney_dc saved={saved}")
