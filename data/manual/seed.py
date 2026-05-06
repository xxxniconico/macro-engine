"""种子数据 V2 — 加入历史金价（用于年涨幅计算）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.storage import save_indicator

# ═══ 历史金价（年均价，美元/盎司）═══
# 来源：LBMA / World Gold Council / Kitco 估算
# ⚠️ 这些是近似值，请根据实际数据更新
GOLD_HISTORY = [
    # (年份-日期, 价格)
    ("2025-05-01", 3200.0),   # 约 2025年5月
    ("2024-05-01", 2350.0),   # 约 2024年5月
    ("2023-05-01", 2000.0),   # 约 2023年5月
    ("2022-05-01", 1870.0),   # 约 2022年5月
    ("2021-05-01", 1820.0),   # 约 2021年5月
    ("2020-05-01", 1720.0),   # 约 2020年5月
    ("2019-05-01", 1290.0),   # 约 2019年5月
    ("2018-05-01", 1310.0),   # 约 2018年5月
]

for dt, price in GOLD_HISTORY:
    save_indicator("gold",              price, dt, "manual", 0.85)
    save_indicator("gold_1y_reference", price, dt, "manual", 0.85)  # 年涨幅参考锚点

print(f"✅ 历史金价: {len(GOLD_HISTORY)} 个数据点")

# ═══ 中国宏观数据 ═══
save_indicator("china_debt_gdp", 297.0, "2025-Q3", "manual", 0.8)
save_indicator("china_pmi", 50.5, "2026-04-01", "manual", 0.9)
save_indicator("china_cpi", 0.1, "2026-01-01", "manual", 0.9)
save_indicator("china_m2_yoy", 7.0, "2026-01-01", "manual", 0.9)

# ═══ 美国宏观数据 ═══
save_indicator("us_debt_gdp", 123.0, "2025-Q3", "manual", 0.8)
save_indicator("us_fed_rate", 4.33, "2025-12-01", "manual", 0.95)
save_indicator("us_cpi", 2.4, "2025-12-01", "manual", 0.9)
save_indicator("us_real_rate", 1.9, "2025-12-01", "manual", 0.8)

# ═══ 帝国周期指标 ═══
save_indicator("usd_reserve_share", 57.4, "2025-Q3", "manual", 0.7)
save_indicator("us_political_polarization", 80, "2024-12-31", "manual", 0.6)
save_indicator("us_wealth_gap", 0.418, "2025-12-31", "manual", 0.6)

print("✅ 种子数据录入完成！")
