"""新浪抓取 V5 — 全指标覆盖（curl 方案，稳定可靠）。

新增: VIXY(恐慌), UUP(美元代理), SHY/IEF(国债收益率代理)
"""

import subprocess, sqlite3
from datetime import date
from pathlib import Path

DB = Path("/home/xxxsuli/macro-engine/macro.db")
today = date.today().isoformat()


def fetch(tickers: str) -> str:
    cmd = ["curl", "-s", "--max-time", "8",
           "-H", "Referer: https://finance.sina.com.cn",
           f"https://hq.sinajs.cn/list={tickers}"]
    result = subprocess.run(cmd, capture_output=True, timeout=10)
    return result.stdout.decode("gbk")


def parse(text: str) -> dict:
    result = {}
    for line in text.strip().split("\n"):
        if "=" not in line:
            continue
        try:
            code = line.split("=")[0].replace("var hq_str_", "")
            d = line.split('"')[1].split(",")
            result[code] = d
        except:
            continue
    return result


def save(name, value):
    conn = sqlite3.connect(str(DB))
    conn.execute(
        "INSERT INTO macro_indicators(indicator_name,value,date,source) "
        "VALUES(?,?,?,?) ON CONFLICT(indicator_name,date,source) "
        "DO UPDATE SET value=excluded.value",
        (name, value, today, "sina"))
    conn.commit()
    conn.close()


saved = 0

# ═══ 1. 美股三大指数 ═══
print("[1/5] 美股指数...")
for code, name in [("gb_inx", "us_sp500"), ("gb_dji", "us_dow"), ("gb_ixic", "us_nasdaq")]:
    try:
        d = parse(fetch(code))
        if code in d and len(d[code]) > 1:
            v = float(d[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

# ═══ 2. 贵金属 ═══
print("[2/7] 贵金属...")
try:
    d = parse(fetch("hf_XAU"))
    if "hf_XAU" in d and len(d["hf_XAU"]) > 0:
        save("gold", float(d["hf_XAU"][0])); saved += 1
        print(f"  ✓ gold={d['hf_XAU'][0]} 昨收={d['hf_XAU'][7]}")
except Exception as e:
    print(f"  ✗ gold: {e}")

# ═══ 2b. WTI 原油 (hf_CL) ═══
print("[3/7] WTI 原油...")
try:
    d = parse(fetch("hf_CL"))
    if "hf_CL" in d and len(d["hf_CL"]) > 0:
        save("oil_wti", float(d["hf_CL"][0])); saved += 1
        print(f"  ✓ oil_wti={d['hf_CL'][0]} 昨收={d['hf_CL'][7]}")
except Exception as e:
    print(f"  ✗ oil_wti: {e}")

# ═══ 2c. 人民币汇率 (USDCNY) ═══
print("[4/7] 人民币汇率...")
try:
    d = parse(fetch("USDCNY"))
    if "USDCNY" in d and len(d["USDCNY"]) > 1:
        # USDCNY: [0]=time, [1]=bid, [2]=ask, [3]=high, [5]=open, [6]=prev_close, [7]=low, [8]=last
        v = float(d["USDCNY"][1])  # bid price
        save("usd_cny", v); saved += 1
        print(f"  ✓ usd_cny={v} (USD/CNY)")
except Exception as e:
    print(f"  ✗ usd_cny: {e}")

# ═══ 3. 核心 ETF（SPY/TLT/GLD/USO）═══
print("[5/7] 核心ETF...")
for code, name in [
    ("gb_spy", "us_spy"),
    ("gb_tlt", "us_tlt"),
    ("gb_gld", "us_gld"),
    ("gb_uso", "us_uso"),
]:
    try:
        d = parse(fetch(code))
        if code in d and len(d[code]) > 1:
            v = float(d[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

# ═══ 4. 宏观代理 ETF（新增）═══
print("[6/7] 宏观代理ETF...")
proxies = [
    ("gb_vixy", "us_vixy"),       # VIX 恐慌指数代理
    ("gb_uup",  "us_uup"),        # 美元 ETF（DXY 代理）
    ("gb_shy",  "us_shy"),        # 1-3年国债 ETF（短端利率代理）
    ("gb_ief",  "us_ief"),        # 7-10年国债 ETF（长端利率代理）
    ("gb_eem",  "em_eem"),        # 新兴市场 ETF（全球风险偏好）
]

for code, name in proxies:
    try:
        d = parse(fetch(code))
        if code in d and len(d[code]) > 1:
            v = float(d[code][1])
            save(name, v); saved += 1
            print(f"  ✓ {name} = {v}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

# ═══ 5. 利率曲线计算 ═══
print("[7/7] 利率曲线...")
try:
    # SHY 和 IEF 的价格差 → 收益率曲线陡峭程度代理
    shy_data = parse(fetch("gb_shy"))
    ief_data = parse(fetch("gb_ief"))
    if "gb_shy" in shy_data and "gb_ief" in ief_data:
        shy = float(shy_data["gb_shy"][1])
        ief = float(ief_data["gb_ief"][1])
        # 短端-长端比：>1 = 倒挂, <1 = 正常
        curve = shy / ief if ief > 0 else 1.0
        save("us_yield_curve", round(curve, 4)); saved += 1
        print(f"  ✓ us_yield_curve = {curve:.4f} (SHY/IEF)")
        
        # 趋势代理：短债 ETF 周变化（周数据需要历史对比，这里先存日值）
        save("us_shy_price", shy); saved += 1
        save("us_ief_price", ief); saved += 1
        print(f"  ✓ SHY={shy} IEF={ief}")
except Exception as e:
    print(f"  ✗ yield_curve: {e}")

print(f"\n✅ sina V5 saved={saved}")
