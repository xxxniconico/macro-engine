"""种子数据 — 首次手动录入关键宏观指标。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.storage import save_indicator

# ═══ 中国宏观数据 ═══
# 来源：BIS / 国家统计局 / 央行
# 注：以下为近似值，请根据最新官方数据更新

# 中国宏观杠杆率（BIS 2025Q3 数据）
save_indicator("china_debt_gdp", 297.0, "2025-Q3", "manual", 0.8)

# PMI（2026年4月 — 请替换为最新值）
save_indicator("china_pmi", 50.5, "2026-04-01", "manual", 0.9)

# CPI 同比
save_indicator("china_cpi", 0.1, "2026-01-01", "manual", 0.9)

# M2 同比增速
save_indicator("china_m2_yoy", 7.0, "2026-01-01", "manual", 0.9)


# ═══ 美国宏观数据 ═══

# 美国债务/GDP
save_indicator("us_debt_gdp", 123.0, "2025-Q3", "manual", 0.8)

# 联邦基金利率
save_indicator("us_fed_rate", 4.33, "2025-12-01", "manual", 0.95)

# CPI 同比
save_indicator("us_cpi", 2.4, "2025-12-01", "manual", 0.9)

# 实际利率
save_indicator("us_real_rate", 1.9, "2025-12-01", "manual", 0.8)


# ═══ 帝国周期指标 ═══

# 美元在全球外汇储备中的份额（IMF COFER 2025Q3）
save_indicator("usd_reserve_share", 57.4, "2025-Q3", "manual", 0.7)

# 美国政治极化指数（Pew Research，百分制估算）
save_indicator("us_political_polarization", 80, "2024-12-31", "manual", 0.6)

# 美国贫富差距 — 前 1% 收入占比
save_indicator("us_wealth_gap", 0.418, "2025-12-31", "manual", 0.6)


print("✅ 种子数据录入完成！")
print("⚠️ 请根据最新官方数据更新上述数值。")
print("   运行 engine/cycle_locator.py 即可看到更新后的诊断。")
