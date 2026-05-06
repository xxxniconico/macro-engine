"""新浪抓取 - 用 curl 子进程绕过 Python requests 超时问题。"""
import subprocess, sqlite3, json
from datetime import date
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/data/macro.db")
today = date.today().isoformat()

def curl_fetch(tickers: str) -> str:
    """通过 curl 获取新浪数据，绕过 Python HTTPS 超时。"""
    cmd = [
        "curl", "-s", "--max-time", "8",
        "-H", "Referer: https://finance.sina.com.cn",
        f"https://hq.sinajs.cn/list={tickers}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.stdout

def parse(text: str) -> dict:
    """解析新浪返回数据。"""
    result = {}
    for line in text.strip().split("\n"):
        if "=" not in line:
            continue
        try:
            code = line.split("=")[0].replace("var hq_str_", "")
            d = line.split('"')[1].split(",")
            result[code] = d
        except (IndexError, ValueError):
            continue
    return result

def save(name, value, src="sina"):
    conn = sqlite3.connect(str(DB))
    conn.execute("""
        INSERT INTO macro_indicators (indicator_name,value,date,source) 
        VALUES(?,?,?,?) 
        ON CONFLICT(indicator_name,date,source) DO UPDATE SET value=excluded.value
    """, (name, value, today, src))
    conn.commit(); conn.close()

# ═══ 主流程 ═══
saved = 0

# 1. 美股三大指数
print("[1/3] 美股...")
data = parse(curl_fetch("gb_inx,gb_dji,gb_ixic"))
for code, name in [("gb_inx","us_sp500"),("gb_dji","us_dow"),("gb_ixic","us_nasdaq")]:
    if code in data and len(data[code]) > 1:
        try:
            v = float(data[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
        except: print(f"  ✗ {name}")

# 2. 黄金
print("[2/3] 贵金属...")
data = parse(curl_fetch("hf_XAU"))
if "hf_XAU" in data and len(data["hf_XAU"]) > 0:
    try:
        v = float(data["hf_XAU"][0])
        save("gold", v); saved += 1
        print(f"  ✓ gold = {v}")
    except: print("  ✗ gold")

# 3. ETF 代理
print("[3/3] ETF...")
data = parse(curl_fetch("gb_spy,gb_tlt,gb_gld,gb_uso"))
for code, name in [("gb_spy","us_spy"),("gb_tlt","us_tlt"),("gb_gld","us_gld"),("gb_uso","us_uso")]:
    if code in data and len(data[code]) > 1:
        try:
            v = float(data[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
        except: print(f"  ✗ {name}")

print(f"\n✅ sina saved={saved}")
