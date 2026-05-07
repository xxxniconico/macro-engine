#!/usr/bin/env python3
"""
P0 数据盲区修补 — V2 (fixed schema + Sina US stock API)
  1. china_real_rate (World Bank FR.INR.RINR + derived)
  2. 中国军事/教育支出 (World Bank)
  3. ETF 历史价格 (SPY/GLD/TLT/SHY via Sina US stock API)
"""
import sqlite3
import json
import urllib.request
import urllib.error
import time
import os

PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJ_ROOT, 'macro.db')

# ── World Bank ───────────────────────────────────────────────────

def wb_fetch(indicator, country='CN', per_page=100):
    url = f'https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page={per_page}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'macro-engine/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if not data or len(data) < 2 or not data[1]:
            return []
        return sorted([(f"{i['date']}-12-31", float(i['value'])) for i in data[1] if i['value'] is not None],
                     key=lambda x: x[0])
    except Exception as e:
        print(f"  ⚠ WB {indicator}: {e}")
        return []

# ── Sina US stock history ────────────────────────────────────────

def sina_us_daily(symbol, length=5000):
    """symbol: spy, gld, tlt, shy (lowercase)"""
    url = f'https://stock.finance.sina.com.cn/usstock/api/json_v2.php/US_MinKService.getDailyK?symbol={symbol}&type=daily&length={length}'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn/'
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        data = json.loads(raw)
        if not data or not isinstance(data, list):
            print(f"  ⚠ Sina {symbol}: unexpected response type ({type(data)})")
            return []
        return sorted([(bar['d'], float(bar['c'])) for bar in data], key=lambda x: x[0])
    except Exception as e:
        print(f"  ⚠ Sina {symbol}: {e}")
        return []

# ── DB insert ────────────────────────────────────────────────────

def insert_records(db, indicator_name, records, source):
    """Schema: UNIQUE(indicator_name, date, source). ON CONFLICT DO UPDATE."""
    count = 0
    for date_str, value in records:
        db.execute('''INSERT INTO macro_indicators(indicator_name, value, date, source, confidence)
            VALUES (?, ?, ?, ?, 0.95)
            ON CONFLICT(indicator_name, date, source) DO UPDATE SET value=excluded.value, confidence=0.95''',
            (indicator_name, value, date_str, source))
        count += 1
    db.commit()
    return count

# ── Main ────────────────────────────────────────────────────────

def main():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    stats = {}

    # ═══ Task 1: china_real_rate ═══
    print("📊 Task 1: china_real_rate — World Bank FR.INR.RINR")
    wb_data = wb_fetch('FR.INR.RINR', 'CN', per_page=100)
    if wb_data:
        print(f"  Fetched {len(wb_data)} recs ({wb_data[0][0]} → {wb_data[-1][0]})")
        n = insert_records(db, 'china_real_rate', wb_data, 'wb_api_direct')
        print(f"  ✅ +{n} records")
        stats['china_real_rate'] = n

    # Derived: china_real_rate = lending_rate - cpi
    print("  🔧 Derived: lending_rate - cpi")
    wb_lending = wb_fetch('FR.INR.LEND', 'CN', per_page=100)
    if wb_lending:
        cpi_rows = db.execute("SELECT date, value FROM macro_indicators WHERE indicator_name='china_cpi' ORDER BY date").fetchall()
        cpi_map = {r[0][:4]: r[1] for r in cpi_rows}
        derived = []
        for date_str, lend_rate in wb_lending:
            year = date_str[:4]
            if year in cpi_map:
                derived.append((date_str, round(lend_rate - cpi_map[year], 2)))
        if derived:
            print(f"  Computed {len(derived)} derived ({derived[0][0]} → {derived[-1][0]})")
            n2 = insert_records(db, 'china_real_rate', derived, 'wb_derived_lend-cpi')
            stats['china_real_rate'] = stats.get('china_real_rate', 0) + n2
            print(f"  ✅ +{n2} derived")

    # ═══ Task 2a: china_military ═══
    print("\n🪖 Task 2a: china_military — WB MS.MIL.XPND.GD.ZS")
    mil = wb_fetch('MS.MIL.XPND.GD.ZS', 'CN', per_page=100)
    if mil:
        print(f"  Fetched {len(mil)} recs ({mil[0][0]} → {mil[-1][0]})")
        n = insert_records(db, 'china_military', mil, 'wb_api')
        print(f"  ✅ +{n} records")
        stats['china_military'] = n

    # ═══ Task 2b: china_education ═══
    print("\n📚 Task 2b: china_education — WB SE.XPD.TOTL.GD.ZS")
    edu = wb_fetch('SE.XPD.TOTL.GD.ZS', 'CN', per_page=100)
    if edu:
        print(f"  Fetched {len(edu)} recs ({edu[0][0]} → {edu[-1][0]})")
        n = insert_records(db, 'china_education', edu, 'wb_api')
        print(f"  ✅ +{n} records")
        stats['china_education'] = n

    # ═══ Task 3: ETF history ═══
    etf_map = {
        'us_spy': 'spy',
        'us_gld': 'gld',
        'us_tlt': 'tlt',
        'us_shy': 'shy',
    }
    for ind_name, sym in etf_map.items():
        print(f"\n📈 Task 3: {ind_name} ({sym}) — Sina US daily K-line")
        bars = sina_us_daily(sym, length=6000)
        if bars:
            print(f"  Fetched {len(bars)} bars ({bars[0][0]} → {bars[-1][0]})")
            for d, v in bars[:2]:
                print(f"    {d} : ${v:.2f}")
            print(f"    ...")
            for d, v in bars[-2:]:
                print(f"    {d} : ${v:.2f}")
            n = insert_records(db, ind_name, bars, 'sina_us_daily')
            print(f"  ✅ +{n} records")
            stats[ind_name] = n
        else:
            stats[ind_name] = 0
        time.sleep(0.5)

    # ── Summary ──
    print("\n" + "="*60)
    print("📊 P0 Summary")
    print("="*60)
    total = 0
    for k, v in stats.items():
        print(f"  {k:<30s} +{v}")
        total += v
    print(f"  {'─'*30}")
    print(f"  TOTAL{' '*25} +{total}")

    # Verify
    print(f"\n🔍 Post-fill:")
    for ind in ['china_real_rate','china_military','china_education','us_spy','us_gld','us_tlt','us_shy']:
        c = db.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM macro_indicators WHERE indicator_name=?", (ind,)).fetchone()
        span = int(c[2][:4]) - int(c[1][:4]) if c[1] and c[2] else 0
        print(f"  {ind:<30s} {c[0]:>5d} recs  {c[1] or '?':>10s} → {c[2] or '?':10s}  ({span}yr)")

    all_count = db.execute("SELECT COUNT(*) FROM macro_indicators").fetchone()[0]
    print(f"\n  Total DB records: {all_count}")

    db.close()

if __name__ == '__main__':
    main()
