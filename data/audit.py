"""数据审计脚本"""
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

DB = Path(__file__).parent.parent / "macro.db"

conn = sqlite3.connect(str(DB))
c = conn.cursor()

# 总览
c.execute("SELECT COUNT(*) FROM macro_indicators")
total = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT indicator_name) FROM macro_indicators")
names = c.fetchone()[0]

print(f"📦 数据库: {total} 条记录, {names} 种指标\n")

# 每种指标的覆盖
c.execute("""
    SELECT indicator_name, COUNT(*) as n, MIN(date) as earliest, MAX(date) as latest
    FROM macro_indicators 
    GROUP BY indicator_name 
    ORDER BY n DESC
""")
rows = c.fetchall()

print(f"{'指标名':<30s} {'记录':>6s} {'最早':>12s} {'最晚':>12s} {'状态'}")
print("-" * 80)

dalio_required = [
    # 短期债务周期
    "china_pmi", "china_cpi", "china_unemployment", "us_vixy",
    "us_yield_curve", "us_sp500", "china_sh_index",
    # 长期债务周期
    "china_debt_gdp", "us_debt_gdp", "gold", "us_fed_rate",
    "usd_reserve_share", "us_real_rate", "china_real_rate",
    # 帝国周期
    "us_political_polarization", "us_wealth_gap",
    # 额外
    "china_gdp_growth", "us_gdp_growth", "us_unemployment",
    "us_cpi", "china_military", "china_education", "us_uso",
    "us_tlt", "em_eem", "credit_spread", "gold_1y_reference",
]

from data.storage import get_snapshot
snap = get_snapshot()

for r in rows:
    name, n, earliest, latest = r
    in_snap = "✅" if name in snap else "❌"
    is_key = "⭐" if name in dalio_required else " "
    print(f"{is_key}{name:<29s} {n:>6d} {earliest:>12s} {latest:>12s} {in_snap}")

# 缺失的关键指标
print(f"\n🔍 Dalio 深度研究要求的指标覆盖:")
missing = []
for req in dalio_required:
    found = req in snap
    val = snap.get(req, {}).get("value", "N/A") if found else "MISSING"
    status = "✅" if found else "❌"
    if not found:
        missing.append(req)
    print(f"  {status} {req:<30s} = {val}")

print(f"\n❌ 缺失: {len(missing)}/{len(dalio_required)}")
if missing:
    for m in missing:
        print(f"     {m}")

# 数据稳定性
print(f"\n📊 数据稳定性（更新频率）:")
c.execute("""
    SELECT indicator_name, MAX(date) as latest,
           COUNT(DISTINCT date) as days_with_data
    FROM macro_indicators
    GROUP BY indicator_name
    HAVING days_with_data < 3
    ORDER BY days_with_data
""")
stale = c.fetchall()
if stale:
    print("  ⚠️ 数据稀少（<3天有数据）:")
    for s in stale:
        print(f"     {s[0]}: {s[2]}天")
else:
    print("  ✅ 所有指标都有足够历史数据")

conn.close()
