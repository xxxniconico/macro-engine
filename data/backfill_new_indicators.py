"""种子 WTI原油 / 人民币汇率 / 美元指数的历史数据，让看板图表有数据可画。"""
import sqlite3
from datetime import date, timedelta

conn = sqlite3.connect('/home/xxxsuli/macro-engine/macro.db')
c = conn.cursor()

# ═══ 1. oil_wti: 用 USO 反推 ═══
RATIO = 1.408  # USO/WTI from 2026-05-08: 134.97/95.85
c.execute("SELECT date, value FROM macro_indicators WHERE indicator_name='us_uso' ORDER BY date")
uso_rows = c.fetchall()

oil_count = 0
for dt, uso_val in uso_rows:
    wti_est = round(uso_val / RATIO, 3)
    c.execute("SELECT 1 FROM macro_indicators WHERE indicator_name='oil_wti' AND date=?", (dt,))
    if not c.fetchone():
        c.execute("INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?)",
                  ("oil_wti", wti_est, dt, "backfill_from_uso"))
        oil_count += 1
print(f"oil_wti backfilled: {oil_count} records")

# ═══ 2. usd_cny: 估算种子 ═══
cny_count = 0
start = date(2025, 5, 1)
end = date(2026, 5, 8)
days = (end - start).days
for i in range(0, days, 3):
    d = start + timedelta(days=i)
    progress = i / days
    if d <= date(2025, 10, 1):
        val = round(7.00 + 0.05 * (1 - i/max(1, (date(2025,10,1)-start).days)), 4)
    elif d <= date(2026, 1, 1):
        val = round(6.85 + 0.10 * ((d - date(2025,10,1)).days / max(1, (date(2026,1,1)-date(2025,10,1)).days)), 4)
    else:
        val = round(6.92 + 0.12 * ((d - date(2026,1,1)).days / max(1, (date(2026,5,8)-date(2026,1,1)).days)), 4)

    c.execute("SELECT 1 FROM macro_indicators WHERE indicator_name='usd_cny' AND date=?", (d.isoformat(),))
    if not c.fetchone():
        c.execute("INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?)",
                  ("usd_cny", val, d.isoformat(), "backfill_estimated"))
        cny_count += 1
print(f"usd_cny backfilled: {cny_count} records")

# ═══ 3. us_uup: 补足历史 ═══
uup_count = 0
for i in range(0, 365, 5):
    d = date(2025, 5, 8) + timedelta(days=i)
    if d >= date(2026, 5, 6):
        break  # 已有真实数据
    val = round(27.2 + 0.8 * (1 if (i//90) % 2 == 0 else -1) + (i/365 - 0.5) * 0.5, 2)
    c.execute("SELECT 1 FROM macro_indicators WHERE indicator_name='us_uup' AND date=?", (d.isoformat(),))
    if not c.fetchone():
        c.execute("INSERT INTO macro_indicators(indicator_name,value,date,source) VALUES(?,?,?,?)",
                  ("us_uup", val, d.isoformat(), "backfill_estimated"))
        uup_count += 1
print(f"us_uup backfilled: {uup_count} records")

conn.commit()

# Verify
for name in ['oil_wti', 'usd_cny', 'us_uup']:
    c.execute('SELECT COUNT(*), MIN(date), MAX(date) FROM macro_indicators WHERE indicator_name=?', (name,))
    row = c.fetchone()
    print(f'  {name}: {row[0]} records, {row[1]} ~ {row[2]}')

conn.close()
print("Done!")
