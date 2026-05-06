"""V2 - 内联版本，极致简单。"""
import requests, sqlite3
from datetime import date
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/data/macro.db")
H = {"Referer": "https://finance.sina.com.cn"}
today = date.today().isoformat()

def s(name, value, src="sina"):
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO macro_indicators (indicator_name,value,date,source) VALUES(?,?,?,?) ON CONFLICT(indicator_name,date,source) DO UPDATE SET value=excluded.value", (name,value,today,src))
    conn.commit(); conn.close()

saved = 0

# --- 美股三大指数 ---
r = requests.get("https://hq.sinajs.cn/list=gb_inx,gb_dji,gb_ixic", headers=H, timeout=10)
t = r.content.decode("gbk")
for line in t.strip().split("\n"):
    if "=" not in line: continue
    try:
        code = line.split("=")[0].replace("var hq_str_", "")
        d = line.split('"')[1].split(",")
        v = float(d[1])
        m = {"gb_inx":"us_sp500","gb_dji":"us_dow","gb_ixic":"us_nasdaq"}
        if code in m:
            s(m[code], v)
            saved += 1
            print(f"  ✓ {m[code]} = {v}")
    except: pass

# --- 黄金 ---
r = requests.get("https://hq.sinajs.cn/list=hf_XAU", headers=H, timeout=10)
t = r.content.decode("gbk")
for line in t.strip().split("\n"):
    if "hf_XAU" in line:
        try:
            d = line.split('"')[1].split(",")
            s("gold", float(d[0])); saved += 1
            print(f"  ✓ gold = {d[0]}")
        except: pass

# --- SPY ETF ---
r = requests.get("https://hq.sinajs.cn/list=gb_spy,gb_tlt,gb_gld,gb_uso", headers=H, timeout=10)
t = r.content.decode("gbk")
m = {"gb_spy":"us_spy","gb_tlt":"us_tlt","gb_gld":"us_gld","gb_uso":"us_uso"}
for line in t.strip().split("\n"):
    if "=" not in line: continue
    try:
        code = line.split("=")[0].replace("var hq_str_", "")
        d = line.split('"')[1].split(",")
        if code in m:
            s(m[code], float(d[1])); saved += 1
            print(f"  ✓ {m[code]} = {d[1]}")
    except: pass

print(f"\n✅ saved={saved}")
