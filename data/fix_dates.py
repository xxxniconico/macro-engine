"""日期标准化脚本 — 对齐所有指标的时间周期。

规则:
  BROKEN (-MM-DD)    → 用同指标最早年份推算
  YYYY-QN            → 转为该季度第一天 YYYY-MM-01 (Q1=01, Q2=04, Q3=07, Q4=10)
  月度指标 (PMI/CPI)  → 统一为 YYYY-MM-01
  年度指标 (Gini等)   → 统一为 YYYY-12-31
  COFER 储备份额      → YYYY-MM-DD (保持季度日期)
  日频行情            → 不做修改
"""

import sqlite3
import re
from pathlib import Path
from datetime import date

DB = Path("/home/xxxsuli/macro-engine/macro.db")

# ═══════════════════════════════════════════════════════
#  指标分类
# ═══════════════════════════════════════════════════════

# 月度发布指标 — 统一到每月1日
MONTHLY_INDICATORS = {
    "china_pmi", "china_cpi", "china_m2_yoy",
    "us_pmi", "us_cpi",
    "china_unemployment", "us_unemployment",
    "china_real_rate",
}

# 年度指标 — 统一到每年12月31日
ANNUAL_INDICATORS = {
    "china_gini", "us_gini",
    "china_education", "china_military",
    "us_political_polarization",
    "china_gdp_growth", "us_gdp_growth",     # World Bank 年度数据
    "us_govt_debt_gdp",
    "china_wealth_gap", "us_wealth_gap",
}

# 季度指标 — Q→月首日
QUARTERLY_FIX = {
    "china_debt_gdp", "us_debt_gdp",
}

# 半年度对齐 (COFER 季度数据保持原样，但 "-MM-DD" 修复)
SEMI_FIX = {
    "usd_reserve_share", "cny_reserve_share", "eur_reserve_share",
}

# 金价年参考 — 固定在每年5月1日
GOLD_REF_FIX = {"gold_1y_reference"}


def fix_broken_date(dt_str, indicator_name, conn):
    """修复缺少年份的日期，从同指标最早完整年份推算。"""
    if not dt_str.startswith("-"):
        return dt_str

    # 从同指标找最早完整年份
    c = conn.execute(
        "SELECT date FROM macro_indicators WHERE indicator_name=? AND date NOT LIKE '-%' ORDER BY date LIMIT 1",
        (indicator_name,))
    row = c.fetchone()
    if row:
        year = row[0][:4]
        return f"{year}{dt_str}"
    # 兜底：用2000年
    return f"2000{dt_str}"


def quarter_to_date(q_str):
    """2025-Q3 → 2025-07-01"""
    m = re.match(r"(\d{4})-Q(\d)", q_str)
    if not m:
        return q_str
    year = int(m.group(1))
    q = int(m.group(2))
    month = {1: "01", 2: "04", 3: "07", 4: "10"}[q]
    return f"{year}-{month}-01"


def align_monthly(dt_str):
    """月度指标统一到当月1日。"""
    m = re.match(r"(\d{4}-\d{2})-\d{2}", dt_str)
    if m:
        return f"{m.group(1)}-01"
    return dt_str


def align_annual(dt_str):
    """年度指标统一到12月31日。"""
    m = re.match(r"(\d{4})-\d{2}-\d{2}", dt_str)
    if m:
        return f"{m.group(1)}-12-31"
    return dt_str


def align_gold_ref(dt_str):
    """金价年参考 → 每年5月1日。"""
    m = re.match(r"(\d{4})-\d{2}-\d{2}", dt_str)
    if m:
        return f"{m.group(1)}-05-01"
    return dt_str


def main():
    conn = sqlite3.connect(str(DB))
    c = conn.cursor()

    # Step 1: 修复 BROKEN 日期
    print("🔧 Step 1: 修复缺少年份的日期...")
    broken = []
    c.execute("SELECT rowid, indicator_name, date FROM macro_indicators WHERE date LIKE '-%'")
    for rowid, name, dt in c.fetchall():
        new_dt = fix_broken_date(dt, name, conn)
        c.execute("UPDATE macro_indicators SET date=? WHERE rowid=?", (new_dt, rowid))
        broken.append((name, dt, new_dt))
        print(f"  {name}: {dt} → {new_dt}")
    conn.commit()
    print(f"  修复 {len(broken)} 条")

    # Step 2: 修复季度格式
    print("\n🔧 Step 2: 修复 YYYY-QN 格式...")
    qfixed = []
    c.execute("SELECT rowid, indicator_name, date FROM macro_indicators WHERE date LIKE '%-Q%'")
    for rowid, name, dt in c.fetchall():
        new_dt = quarter_to_date(dt)
        if new_dt != dt:
            c.execute("UPDATE macro_indicators SET date=? WHERE rowid=?", (new_dt, rowid))
            qfixed.append((name, dt, new_dt))
            print(f"  {name}: {dt} → {new_dt}")
    conn.commit()
    print(f"  修复 {len(qfixed)} 条")

    # Step 3: 月度指标对齐
    print("\n🔧 Step 3: 月度指标日期对齐到每月1日...")
    mfixed = 0
    placeholders = ",".join(["?"] * len(MONTHLY_INDICATORS))
    c.execute(
        f"SELECT rowid, indicator_name, date FROM macro_indicators WHERE indicator_name IN ({placeholders})",
        list(MONTHLY_INDICATORS))
    for rowid, name, dt in c.fetchall():
        new_dt = align_monthly(dt)
        if new_dt != dt:
            c.execute("UPDATE macro_indicators SET date=? WHERE rowid=?", (new_dt, rowid))
            mfixed += 1
    conn.commit()
    print(f"  修复 {mfixed} 条")

    # Step 4: 年度指标对齐
    print("\n🔧 Step 4: 年度指标日期对齐到12月31日...")
    afixed = 0
    placeholders = ",".join(["?"] * len(ANNUAL_INDICATORS))
    c.execute(
        f"SELECT rowid, indicator_name, date FROM macro_indicators WHERE indicator_name IN ({placeholders})",
        list(ANNUAL_INDICATORS))
    for rowid, name, dt in c.fetchall():
        new_dt = align_annual(dt)
        if new_dt != dt:
            c.execute("UPDATE macro_indicators SET date=? WHERE rowid=?", (new_dt, rowid))
            afixed += 1
    conn.commit()
    print(f"  修复 {afixed} 条")

    # Step 5: 金价年参考对齐
    print("\n🔧 Step 5: 金价年参考对齐到5月1日...")
    gfixed = 0
    c.execute("SELECT rowid, indicator_name, date FROM macro_indicators WHERE indicator_name='gold_1y_reference'")
    for rowid, name, dt in c.fetchall():
        new_dt = align_gold_ref(dt)
        if new_dt != dt:
            c.execute("UPDATE macro_indicators SET date=? WHERE rowid=?", (new_dt, rowid))
            gfixed += 1
    conn.commit()
    print(f"  修复 {gfixed} 条")

    # Step 6: 去重 (同 indicator+date+source → 保留最新 value)
    print("\n🔧 Step 6: 去重...")
    c.execute("""
        DELETE FROM macro_indicators WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM macro_indicators
            GROUP BY indicator_name, date, source
        )
    """)
    removed = c.rowcount
    conn.commit()
    print(f"  删除 {removed} 条重复")

    # Step 7: 最终验证
    print("\n✅ 最终验证:")
    c.execute("SELECT COUNT(*) FROM macro_indicators")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT indicator_name) FROM macro_indicators")
    ni = c.fetchone()[0]
    print(f"  总记录: {total} | 指标种类: {ni}")

    # 检查是否还有异常日期
    c.execute("SELECT COUNT(*) FROM macro_indicators WHERE date LIKE '-%'")
    broken_left = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM macro_indicators WHERE date LIKE '%-Q%'")
    q_left = c.fetchone()[0]
    print(f"  遗留学年: {broken_left} | 遗留季度: {q_left}")

    conn.close()
    print("\n✅ 日期标准化完成！")


if __name__ == "__main__":
    main()
