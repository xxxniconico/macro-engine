"""回填真实历史数据 — WTI原油 / 美元UUP / 人民币汇率

数据来源:
- UUP: 新浪美股K线 (2007-03-01 至今, 4827条)
- WTI原油: 通过 USO ETF 新浪K线反推 (2006-04-10 至今, 5050条)
- USD/CNY: 新浪外汇日K线 (1994-08-30 至今)

USO/WTI 换算: 取最近30日均值计算比例，用此比例回推全部历史
"""
import subprocess, sqlite3, json, time
from pathlib import Path
from datetime import date

DB = Path("/home/xxxsuli/macro-engine/macro.db")
TODAY = date.today().isoformat()

def fetch_json(url):
    cmd = ["curl", "-s", "--max-time", "15", url]
    result = subprocess.run(cmd, capture_output=True, timeout=20)
    return result.stdout.decode("utf-8", errors="replace")

def fetch_forex_raw(url):
    cmd = ["curl", "-s", "--max-time", "15", url]
    result = subprocess.run(cmd, capture_output=True, timeout=20)
    return result.stdout.decode("gbk", errors="replace")

conn = sqlite3.connect(str(DB))
c = conn.cursor()

# ═══════════ 1. UUP 历史 (新浪美股K线) ═══════════
print("[1/3] 获取 UUP 历史...")
try:
    raw = fetch_json(
        "https://stock.finance.sina.com.cn/usstock/api/json_v2.php/US_MinKService.getDailyK?symbol=uup&type=daily&length=6000"
    )
    uup_data = json.loads(raw)
    print(f"  获取 {len(uup_data)} 条 UUP K线")

    uup_count = 0
    for bar in uup_data:
        dt = bar["d"]
        close = float(bar["c"])
        c.execute("SELECT 1 FROM macro_indicators WHERE indicator_name='us_uup' AND date=? AND source='sina_kline'", (dt,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?)",
                ("us_uup", close, dt, "sina_kline"))
            uup_count += 1
    print(f"  回填 {uup_count} 条 (2007-03 ~ 今)")
except Exception as e:
    print(f"  ✗ UUP: {e}")

# ═══════════ 2. WTI 原油 (通过 USO K线反推) ═══════════
print("[2/3] 获取 USO → WTI...")
try:
    raw = fetch_json(
        "https://stock.finance.sina.com.cn/usstock/api/json_v2.php/US_MinKService.getDailyK?symbol=uso&type=daily&length=6000"
    )
    uso_data = json.loads(raw)
    print(f"  获取 {len(uso_data)} 条 USO K线")

    # 计算换算比例: 最近30天 USO/WTI 均值
    # 先取已有真实 WTI 数据点
    c.execute("SELECT AVG(value) FROM macro_indicators WHERE indicator_name='oil_wti' AND source='sina'")
    wti_avg = c.fetchone()[0] or 95.85
    
    # 取最近30天 USO 均值
    recent_uso = [float(b["c"]) for b in uso_data[-30:]]
    uso_avg = sum(recent_uso) / len(recent_uso)
    ratio = uso_avg / wti_avg
    print(f"  USO/WTI 比率 = {uso_avg:.2f}/{wti_avg:.2f} = {ratio:.4f}")

    oil_count = 0
    for bar in uso_data:
        dt = bar["d"]
        uso_close = float(bar["c"])
        wti_est = round(uso_close / ratio, 3)
        c.execute("SELECT 1 FROM macro_indicators WHERE indicator_name='oil_wti' AND date=? AND source='sina_kline'", (dt,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?)",
                ("oil_wti", wti_est, dt, "sina_kline"))
            oil_count += 1
    print(f"  回填 {oil_count} 条 WTI (2006-04 ~ 今, via USO/{ratio:.4f})")
except Exception as e:
    print(f"  ✗ WTI: {e}")

# ═══════════ 3. USD/CNY 历史 (新浪外汇日K线) ═══════════
print("[3/3] 获取 USD/CNY 历史...")
try:
    raw = fetch_forex_raw(
        "https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/var%20t=/NewForexService.getDayKLine?symbol=USDCNY"
    )
    # 格式: var t=("1994-08-30,8.5616,8.5616,8.5616,8.5616,|1994-08-31,...")
    # 去掉前缀, 按 | 分割, 每条: date,open,high,low,close
    data_str = raw.split('("')[1].split('")')[0] if '("' in raw else raw
    bars = [b for b in data_str.split("|") if b.count(",") >= 4]
    print(f"  获取 {len(bars)} 条 CNY K线")

    cny_count = 0
    for bar in bars:
        parts = bar.split(",")
        dt = parts[0]
        close = float(parts[4])  # 收盘价
        if dt < "1995-01-01":
            continue  # 跳过1994年锚定前数据
        c.execute("SELECT 1 FROM macro_indicators WHERE indicator_name='usd_cny' AND date=? AND source='sina_forex'", (dt,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?)",
                ("usd_cny", close, dt, "sina_forex"))
            cny_count += 1
    print(f"  回填 {cny_count} 条 CNY (1995-01 ~ 今)")
except Exception as e:
    print(f"  ✗ CNY: {e}")

# ═══════════ 验证 ═══════════
conn.commit()
print("\n=== 回填结果 ===")
for name in ['us_uup', 'oil_wti', 'usd_cny']:
    c.execute("""SELECT COUNT(*), MIN(date), MAX(date), 
        (SELECT value FROM macro_indicators WHERE indicator_name=? ORDER BY date DESC LIMIT 1)
        FROM macro_indicators WHERE indicator_name=?""", (name, name))
    row = c.fetchone()
    print(f"  {name}: {row[0]} records, {row[1]} ~ {row[2]}, latest={row[3]}")

conn.close()
print("✅ 完成!")
