# Dalio 引擎 — 学术/历史数据增补方案

**生成日期**: 2026-05-07  
**当前状态**: 44 指标，28/28 Dalio 覆盖，但 22 指标 <5 年历史

---

## 一、当前数据诊断

### 1.1 覆盖度：看似完整，深度不足

| 层级 | 指标数 | 覆盖 | 平均跨度 | 评价 |
|---|---|---|---|---|
| 短周期 | 10/10 ✓ | 100% | 2-30yr | PMI/CPI 有 30 年，但 S&P 500/VIX 仅 3 年 |
| 长债务周期 | 6/6 ✓ | 100% | **0-8yr** | ⚠ 债务/GDP 仅 1 条！黄金仅 8 年 |
| 帝国周期 | 8/8 ✓ | 100% | **0-26yr** | ⚠ 极化度仅 1 条，贫富差距 1-3 条 |
| 交叉市场 | 4/4 ✓ | 100% | 0-3yr | 全部不足 3 年 |

### 1.2 最严重缺口（仅 1-2 条记录）

| 指标 | 记录数 | 现有范围 | 最低要求 | 对引擎影响 |
|---|---|---|---|---|
| `china_debt_gdp` | 1 | 2025-07 | 1995-2026 | 长债务周期定位**完全失能** |
| `us_debt_gdp` | 1 | 2025-07 | 1940-2026 | 同上 |
| `china_real_rate` | 1 | 2026-05 | 2000-2026 | 去杠杆判断无依据 |
| `credit_spread` | 1 | 2026-05 | 1990-2026 | 信贷紧缩检测失准 |
| `us_political_polarization` | 1 | 2024-12 | 1980-2026 | 帝国周期判断失能 |
| `us_wealth_gap` | 3 | 2025-2026 | 1980-2026 | 贫富差距趋势不可见 |
| `china_wealth_gap` | 2 | 2026-12 | 2000-2026 | 同上 |

### 1.3 历史长度不足（<5 年）

黄金、VIX、利率、收益率曲线等核心市场指标仅回溯到 2023-2024 年。Dalio 的长周期理论需要**至少 50 年**数据才能验证。

---

## 二、增补策略：三层金字塔

```
        ┌──────────────┐
        │ 超长期历史   │  ← 1870+  百年尺度
        │ (BIS/JST/   │     债务·利率·GDP·危机
        │  Maddison)  │     用于长周期/帝国周期
        ├──────────────┤
        │ 学术深度数据 │  ← 1950+  半世纪
        │ (WID/FSB/   │     贫富差距·影子银行·极化
        │  V-Dem/GPR) │     用于系统动力/第一性
        ├──────────────┤
        │ 市场高频数据 │  ← 1990+  30年
        │ (FRED/Bloom)│     利率·利差·波动率·房价
        │              │     用于短周期/叙事
        └──────────────┘
```

### 为什么需要超长期数据？

Dalio 框架本质是**跨世纪比较**：
- 短期债务周期 ~7 年 → 需要 3-4 个完整周期 = 21-28 年
- 长期债务周期 ~75 年 → 需要 2 个完整周期 = 150 年
- 帝国周期 ~250 年 → 需要至少 1 个完整周期

当前最长的数据是 CPI（30 年），远不够支撑帝国周期分析。**必须引入学术长期数据库。**

---

## 三、具体增补清单

### 3.1 超长期历史（1870+）

| 数据源 | 新增指标 | 时间范围 | 频率 | 对 Dalio 框架的价值 |
|---|---|---|---|---|
| **Jordà-Schularick-Taylor Macrohistory** | 实际 GDP、CPI、信贷/GDP、政策利率、长期利率、房价、股市回报 | 1870-2020 (18国) | 年 | 长债务周期**核心数据源**。直接提供 150 年信贷周期证据 |
| **Maddison Project** | 人均 GDP、人口、GDP（1990 国际元） | 1-2018 AD | 年 | 帝国兴衰的定量锚点 |
| **Reinhart-Rogoff** | 主权违约、银行危机、通胀危机日期 | 1800-2020 (70国) | 事件 | 补充 29 个历史模板，增加危机类比精度 |
| **BIS Total Credit** | 非金融部门信贷/GDP 缺口 | 1961-2026 | 季 | 直接替换当前单点 `debt_gdp` |
| **IMF IFS** | 政策利率、国债收益率、汇率 | 1948-2026 | 月/季 | 回填 Fed 利率至 1954 年 |

### 3.2 学术深度数据（1950+）

| 数据源 | 新增指标 | 时间范围 | 频率 | 对 Dalio 框架的价值 |
|---|---|---|---|---|
| **WID.world (Piketty)** | 前 1%/10% 财富份额、Gini（税后）、收入份额 | 1913-2023 | 年 | **贫富差距的学术金标准**。替换当前 1-3 条 Gini/wealth_gap |
| **V-Dem Institute** | 政治极化指数、民主质量、公民社会强度 | 1900-2023 (202国) | 年 | 替换单点 `political_polarization` |
| **Caldara & Iacoviello GPR** | 地缘政治风险指数（GPR） | 1900-2026 | 月 | 新增！博弈终局模块的定量输入 |
| **FSB GMR** | 非银行金融中介（影子银行）规模 | 2002-2026 | 年 | 新增！系统动力模块的薄弱环节 |
| **Baker-Bloom-Davis EPU** | 经济政策不确定性指数 | 1985-2026 | 月 | 新增！增强叙事模块定量基础 |
| **FRED (St. Louis Fed)** | 10Y-2Y 利差、TED spread、Baa-Aaa spread、Case-Shiller | 1953-2026 | 日/月 | 回填利率曲线、信用利差至合理历史 |

### 3.3 市场高频回填（1990+）

| 数据源 | 指标 | 当前范围 | 目标范围 | 优先度 |
|---|---|---|---|---|
| FRED | `us_fed_rate` | 2024-2026 | 1954-2026 | 🔴 |
| FRED | `us_yield_curve` | 2024-2026 | 1976-2026 | 🔴 |
| FRED | `us_real_rate` | 2024-2026 | 2003-2026 | 🔴 |
| FRED | `us_sp500` | 2023-2026 | 1950-2026 | 🟡 |
| FRED | `us_vixy` | 2023-2026 | 1990-2026 | 🟡 |
| FRED | `gold` | 2018-2026 | 1971-2026 | 🔴 |
| FRED | `credit_spread` | 2026-05 | 1997-2026 | 🔴 |

---

## 四、实施路线图

### Phase 1: 救急补洞（1-2h）🔴

回填**当前只有 1-2 条记录**的指标，使引擎核心逻辑可运行：

```bash
# FRED 批量抓取（免费 API，无需注册）
python3 data/fetchers/fred_backfill.py \
  --series DGS10,DGS2,DFF,T10YIE,SP500,VIXCLS,GOLDAMGBD228NLBR \
  --start 1990-01-01

# BIS Total Credit 回填
python3 data/fetchers/bis_credit.py \
  --countries US,CN --start 1995

# WID 贫富差距
python3 data/fetchers/wid_gini.py \
  --countries US,CN --start 1980
```

### Phase 2: 学术深度（3-4h）🟡

引入完整学术数据集，覆盖 1950+ 历史：

```bash
# V-Dem 政治极化
python3 data/fetchers/vdem_polarization.py

# GPR 地缘政治风险
python3 data/fetchers/gpr_index.py

# EPU 政策不确定性
python3 data/fetchers/epu_index.py --countries US,CN

# FSB 影子银行
python3 data/fetchers/fsb_shadow_banking.py
```

### Phase 3: 百年尺度（4-6h）🟢

引入 JST Macrohistory，覆盖 1870-2020：

```bash
# JST Macrohistory Database
python3 data/fetchers/jst_macrohistory.py

# 自动生成：信贷/GDP→长周期分数、房市→泡沫检测基线
python3 data/fetchers/jst_to_dalio.py

# Maddison Project
python3 data/fetchers/maddison_gdp.py
```

---

## 五、技术方案

### 5.1 数据获取方式

所有数据源均为**公开免费**的学术/政府数据库：

| 数据源 | 获取方式 | 格式 | 是否需要注册 |
|---|---|---|---|
| FRED | `pip install fredapi` + 免费 API key | JSON | 是（免费） |
| BIS | `requests` → bulk download CSV | CSV | 否 |
| WID.world | `pip install wid` 或 API | CSV/JSON | 否 |
| V-Dem | Bulk download → 本地解析 | CSV | 否 |
| GPR | Excel download → pandas | XLSX | 否 |
| JST Macrohistory | Excel download → pandas | XLSX | 否 |
| Maddison | Excel download → pandas | XLSX | 否 |
| FSB | PDF → 手动提取 / 爬虫 | PDF | 否 |

### 5.2 存储策略

所有新增数据存入现有 `macro.db`，**不改变表结构**：
- `macro_indicators` 表已支持任意 `indicator_name` + `date` + `value`
- 新增指标直接 `INSERT`，无需 migration
- 历史回填使用 `INSERT OR REPLACE` 避免重复

### 5.3 频率映射

| 源频率 | 目标频率 | 日期标准化 |
|---|---|---|
| 日频 (FRED daily) | 月频（取月末值） | `YYYY-MM-01` |
| 月频 (FRED monthly) | 月频 | `YYYY-MM-01` |
| 季频 (BIS quarterly) | 季频 | `YYYY-QN-01` |
| 年频 (WID, V-Dem, JST) | 年频 | `YYYY-12-31` |

---

## 六、预期收益

| 维度 | 当前状态 | Phase 1 后 | Phase 2 后 | Phase 3 后 |
|---|---|---|---|---|
| 总数据点 | 583 | ~1,500 | ~3,000 | ~5,000+ |
| 平均历史跨度 | 5 年 | 25 年 | 50 年 | 100+ 年 |
| 长债务周期验证 | ❌ 无法验证 | ⚠ 部分可验证 | ✅ 1.5 周期 | ✅ 完整周期 |
| 帝国周期判断 | ❌ 单点数据 | ⚠ 30 年趋势 | ✅ 70 年趋势 | ✅ 130 年趋势 |
| 历史类比精度 | 低（29 个模板无数据支撑） | 中 | 高 | 极高 |
| 压力测试基线 | 短（5 年 max） | 中 | 长 | 超长 |

---

## 七、优先建议

**如果只做一件事**：先回填 `china_debt_gdp` 和 `us_debt_gdp` 到 1995 年（BIS 数据免费直接下载），这两个指标是长周期判断的骨架，现在各只有 1 条记录，引擎的长周期模块完全空转。

**如果做三件事**：加上 FRED 回填 Fed 利率 + 收益率曲线，这样短周期和信贷分析就有历史基线。

**如果要让 Dalio 框架真正"活起来"**：必须引入 JST Macrohistory Database——1870-2020 的 18 国信贷/GDP/房价/利率面板数据，是学术界做长周期研究的**唯一公认标准**。有了它，引擎才能真正做"这次像 1937 年还是 2007 年"的比较。

---

*关联文档：[[Dalio 引擎执行复盘 2024-05-06]] · [[项目]]*
