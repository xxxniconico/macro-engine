# 手动录入数据

## 为什么要手动录入？

Dalio 的框架需要跨越几十年的宏观数据（债务/GDP、央行独立性、政治极化等），
这些数据无法通过实时 API 获取。需要定期手动录入。

## 录入方式

在 Python 中运行：

```python
from data.storage import save_indicator
from datetime import date

# 中国宏观杠杆率（季度更新）
save_indicator("china_debt_gdp", 297.0, "2025-Q4", "manual", 0.8)

# CPI（月度更新）
save_indicator("china_cpi", 0.1, "2026-04-01", "manual", 0.9)

# PMI（月度更新）
save_indicator("china_pmi", 49.5, "2026-04-01", "manual", 0.9)

# M2 同比增速
save_indicator("china_m2_yoy", 7.0, "2026-04-01", "manual", 0.9)

# 美元储备货币份额（季度更新）
save_indicator("usd_reserve_share", 57.4, "2025-Q4", "manual", 0.7)

# 美国政治极化指数（年度更新）
save_indicator("us_political_polarization", 78, "2025-12-31", "manual", 0.6)

# 美国贫富差距 - 基尼系数
save_indicator("us_wealth_gap", 0.415, "2025-12-31", "manual", 0.6)

# 实际利率（名义利率 - CPI）
save_indicator("china_real_rate", -0.5, "2026-04-01", "manual", 0.8)
```

## 数据来源

| 指标 | 来源 | 更新频率 |
|------|------|---------|
| 中国债务/GDP | BIS / CNBS | 季度 |
| PMI | 国家统计局 | 月度 |
| CPI | 国家统计局 | 月度 |
| M2 | 央行 | 月度 |
| 美元储备份额 | IMF COFER | 季度 |
| 政治极化 | Pew Research | 年度 |
| 贫富差距 | World Inequality DB | 年度 |

## 首次录入命令

```bash
cd ~/macro-engine
~/.hermes/hermes-agent/venv/bin/python data/manual/seed.py
```
