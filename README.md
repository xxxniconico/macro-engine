# 🔮 Dalio Macro Engine

> Ray Dalio 宏观协同分析系统 — 本地运行的 10 模块 AI 引擎  
> 60+ 指标 · 22,000+ 数据点 · 1870–2026 跨度

---

## 概览

基于 Ray Dalio《原则：应对变化中的世界秩序》方法论，构建的**多视角交叉验证宏观分析引擎**。不是单一指标仪表盘，而是将 8 个分析视角通过 6 步流水线合成为统一的风险判断和资产配置建议。

### 核心能力

```
📊 数据层 (SQLite)           → 60+ 指标 × 6 频率层级
🔄 3 周期框架                → 短期债务 (7yr) / 长期债务 (75yr) / 帝国兴衰 (250yr)
🧩 10 引擎模块               → 模板匹配 · 周期定位 · 因果推理 · 博弈论 · 压力测试
🎯 协同总指挥                → 动态权重 · 风险得分 · 仓位分配
📈 交互看板                  → 纯 HTML/CSS/JS · 暗色主题 · 6 Tab
```

### 当前风险判断（实时）

运行 `python3 engine/orchestrator.py --full` 获取最新分析。当前模型输出：

- **宏观阶段**: 秩序更替期（全球秩序重组，储备货币动摇）
- **风险得分**: 45/100（🟠 谨慎 — 降低权益，增持对冲）
- **仓位建议**: 35% 权益 / 20% 黄金 / 40% 债券 / 5% 现金

---

## 快速开始

### 前置要求

- Python 3.9+
- 可访问国际 API（World Bank、Sina Finance）的网络环境
- 建议 WSL/Linux 环境

### 安装

```bash
git clone <repo-url> macro-engine
cd macro-engine

# 初始化数据库并回填历史数据
python3 data/storage.py                    # 建表
python3 data/fetchers/phase1_backfill.py   # Phase 1: 中美宏观基础
python3 data/fetchers/phase2_academic.py   # Phase 2: 学术数据 (GPR/EPU)
python3 data/fetchers/phase3_jst.py        # Phase 3: JST 百年数据
python3 data/fetchers/p0_gap_fill.py       # P0: ETF 日频 + WB 补丁

# 首次全量分析 + 导出
python3 dashboard/export_data.py
```

### 启动看板

```bash
cd dashboard
python3 serve_nocache.py 8502 &
# 浏览器打开 http://localhost:8502
```

> ⚠️ **不要用 `python3 -m http.server`** — 它不发送 `Cache-Control` 头，浏览器会缓存旧版 HTML。`serve_nocache.py` 强制 `no-cache`。

### 定时更新

```bash
# 配置 cron（需 hermes cronjob 或系统 crontab）
bash scripts/update_daily.sh     # 每日交易数据 (Mon-Fri 08:00)
bash scripts/update_monthly.sh   # 月度宏观数据 (每月1日)
bash scripts/update_quarterly.sh # 季度数据 (1/4/7/10月5日)
bash scripts/update_annual.sh    # 年度数据 (每年1月15日)
```

---

## 架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        DATA LAYER (SQLite)                        │
│   Tier 0: Academic    — GPR, EPU, Shadow Banking, V-Dem          │
│   Tier 1: Daily       — SP500, VIX, Gold, ETFs (Sina)            │
│   Tier 2: Monthly     — PMI, CPI, M2, Unemployment               │
│   Tier 3: Quarterly   — GDP, Debt/GDP (World Bank)               │
│   Tier 4: Annual      — Gini, COFER, Education, Military         │
│   Tier 5: Computed    — Real rates, Credit spread, Wealth gap    │
│   Tier 6: Centennial  — JST Macrohistory R6 (1870-2020)          │
├──────────────────────────────────────────────────────────────────┤
│  STEP 1: Template Matching    → 29 historical crisis analogs     │
│  STEP 2: Cycle Positioning    → Short/Long/Empire diagnosis      │
│  STEP 3: Causal Inference     → 50-node DAG, trend-aware trigger │
│  STEP 4: Game Theory          → 6-player, 3-step lookahead       │
│  STEP 5: Stress Testing       → 28 scenarios, sigmoid probability│
│     [Supplemental Modules]                                        │
│     Narrative V2   ← media crawl, sentiment, tipping points      │
│     System Dynamics V2 ← stabilizers/amplifiers, A/S ratio       │
│     First Principles  ← 8 reduction chains, trigger logic        │
│     Historical Diff   ← template vs current, better/worse        │
│     Divergence Detector ← 5-pair indicator divergence check      │
├──────────────────────────────────────────────────────────────────┤
│  STEP 6: ORCHESTRATOR SYNTHESIS                                  │
│  Continuous phase scoring → dynamic weights → risk score → alloc │
└──────────────────────────────────────────────────────────────────┘
```

### 项目结构

```
macro-engine/
├── engine/                    # 核心引擎模块
│   ├── orchestrator.py        # 协同总指挥 (6步流水线)
│   ├── template_matcher.py    # 历史模板匹配
│   ├── cycle_locator.py       # 3周期定位
│   ├── causal_chain.py        # 50节点因果图
│   ├── game_theory_v2.py      # 博弈论 V2 (sigmoid)
│   ├── stress_test_v2.py      # 压力测试 V2
│   ├── narrative_v2.py        # 叙事分析 V2
│   ├── system_dynamics_v2.py  # 系统动力学 V2
│   ├── first_principles.py    # 第一性原理
│   ├── historical_diff.py     # 历史差异
│   ├── divergence_detector.py # 背离检测
│   └── p1_validation.py       # P1 回溯+灵敏度+校准
├── data/                      # 数据层
│   ├── storage.py             # SQLite 建表
│   ├── fetchers/              # 数据摄取器
│   │   ├── sina_v5.py         # 新浪实时行情
│   │   ├── eastmoney_macro.py # 东方财富宏观
│   │   ├── worldbank.py       # 世界银行 API
│   │   ├── phase1_backfill.py # Phase 1 回填
│   │   ├── phase2_academic.py # Phase 2 学术
│   │   ├── phase3_jst.py      # Phase 3 JST 百年
│   │   └── p0_gap_fill.py     # P0 数据补丁
│   └── manual/                # 手动种子数据
│       ├── seed.py            # 初始化数据
│       └── templates.py       # 29 历史模板
├── dashboard/                 # 纯 HTML 看板
│   ├── index.html             # 看板主文件 (1500+ 行)
│   ├── export_data.py         # DB → JSON 导出
│   ├── serve_nocache.py       # HTTP 服务 (强制 no-cache)
│   └── data.json              # 导出数据 (573KB, gitignored)
├── scripts/                   # 更新脚本
│   ├── update_daily.sh
│   ├── update_monthly.sh
│   ├── update_quarterly.sh
│   └── update_annual.sh
└── macro.db                   # SQLite 数据库 (gitignored)
```

---

## 数据来源

| 数据 | 来源 | 频率 | 跨度 |
|---|---|---|---|
| 中美 PMI/CPI/GDP | 东方财富 + 世界银行 | 月/季 | 1990s+ |
| 标普500/VIX/黄金/ETF | 新浪财经 (`hq.sinajs.cn`) | 日 | 2001+ |
| ETF 历史日线 | 新浪美股 K线 API | 日 | 2001+ |
| 国债/GDP 长序列 | 世界银行 API | 年 | 1990s+ |
| 地缘风险 GPR | Caldara-Iacoviello 论文 | 月 | 1900-2026 |
| 经济政策不确定 EPU | policyuncertainty.com | 月 | 1985-2026 |
| 影子银行 | FSB GMR | 年 | 2002-2025 |
| 政治极化 | V-Dem v13 | 年 | 1900-2023 |
| 150年宏观数据 | JST Macrohistory R6 | 年 | 1870-2020 |
| 军费/教育支出 | 世界银行 | 年 | 1971+ |
| 基尼系数/财富差距 | 世界银行 + WID | 年 | 1990s+ |
| COFER 储备份额 | IMF (估算回填) | 季 | 2010s+ |

---

## 引擎升级日志

### V2 (2026-04)
- 全部引擎模块从硬编码阈值升级为 sigmoid 连续函数
- 协同总指挥从二元决策树 → 连续 5 相评分 + 模糊权重混合
- 因果链从二元触发 → 趋势感知 + 强度分数
- 博弈论从 if/else → sigmoid 可行性

### P0 数据补丁 (2026-05)
- `china_real_rate`: 1 → 75 条 (1980-2026)
- `china_military/education`: 2 → 38/28 条
- ETF 日频历史: 2 → 16,557 条 (SPY/GLD/TLT/SHY)

### P1 校准 (2026-05)
- 灵敏度分析: 5 大风险驱动力识别
- 6 项 sigmoid 阈值落地校准
- 风险得分 45/100 (秩序更替期)

---

## .gitignore

```
macro.db
dashboard/data.json
dashboard/p1_report.json
logs/
__pycache__/
*.pyc
```

---

## 许可

MIT — 仅供学术研究和学习使用。JST Macrohistory 数据受学术许可保护，不得再分发原始数据。
