"""新浪抓取 V4 - 正确的编码处理。"""
import subprocess, sqlite3
from datetime import date
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/macro.db")
today = date.today().isoformat()

def fetch(tickers: str) -> str:
    """curl 抓取新浪，手动 gbk 解码。"""
    cmd = ["curl", "-s", "--max-time", "8",
           "-H", "Referer: https://finance.sina.com.cn",
           f"https://hq.sinajs.cn/list={tickers}"]
    result = subprocess.run(cmd, capture_output=True, timeout=10)
    return result.stdout.decode("gbk")

def parse(text: str) -> dict:
    result = {}
    for line in text.strip().split("\n"):
        if "=" not in line: continue
        try:
            code = line.split("=")[0].replace("var hq_str_", "")
            d = line.split('"')[1].split(",")
            result[code] = d
        except: continue
    return result

def save(name, value):
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?) ON CONFLICT(indicator_name,date,source) DO UPDATE SET value=excluded.value", (name, value, today, "sina"))
    conn.commit(); conn.close()

saved = 0

# 1. 美股
print("[1/3] 美股...")
for code, name in [("gb_inx","us_sp500"),("gb_dji","us_dow"),("gb_ixic","us_nasdaq")]:
    try:
        d = parse(fetch(code))
        if code in d and len(d[code]) > 1:
            v = float(d[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
    except Exception as e: print(f"  ✗ {name}: {e}")

# 2. 黄金
print("[2/3] 贵金属...")
try:
    d = parse(fetch("hf_XAU"))
    if "hf_XAU" in d and len(d["hf_XAU"]) > 0:
        save("gold", float(d["hf_XAU"][0])); saved += 1
        print(f"  ✓ gold={d['hf_XAU'][0]} 昨收={d['hf_XAU'][7]}")
except Exception as e: print(f"  ✗ gold: {e}")

# 3. ETF
print("[3/3] ETF...")
for code, name in [("gb_spy","us_spy"),("gb_tlt","us_tlt"),("gb_gld","us_gld"),("gb_uso","us_uso")]:
    try:
        d = parse(fetch(code))
        if code in d and len(d[code]) > 1:
            v = float(d[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
    except Exception as e: print(f"  ✗ {name}: {e}")

print(f"\n✅ sina saved={saved}")
