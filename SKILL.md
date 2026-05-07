---
name: dalio-macro-analysis-system
description: "Complete methodology for building a Ray Dalio-inspired multi-perspective macroeconomic analysis system with Bayesian triangulation, meta-learning, and interactive dashboard. Covers architecture, data pipeline, engine design, calibration, and deployment."
version: 3.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [macro, dalio, bayesian, meta-learning, system-design, data-science, investing]
    related_skills: [systematic-debugging, writing-plans, stock-market-data, obsidian]
---

# Dalio 宏观分析系统 — 完整方法论

## 系统概览

基于 Ray Dalio《原则：应对变化中的世界秩序》构建的**本地宏观分析引擎**。从 MVP 迭代到 V3.1，包含 20 个引擎模块，60+ 指标，22,000+ 时序点，1870-2026 年跨度。

```
版本进化:
  V1 (MVP):   数据管道 + 10引擎 + 加权平均 + Streamlit看板
  V2:         Sigmoid连续化 → 全部模块从硬编码升级
  V3:         贝叶斯三角验证 → 代替加权平均
  V3.1:       元学习 → 自适应模块可靠性
  P0-P2:      数据补丁 + 校准 + 体验完善
```

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    DATA LAYER (SQLite)                        │
│  Tier 0: Academic (GPR/EPU/Shadow/V-Dem)                     │
│  Tier 1: Daily (Sina: SPY/GLD/TLT/SHY/VIX/Gold)             │
│  Tier 2: Monthly (PMI/CPI/Unemp 东方财富+WorldBank)          │
│  Tier 3: Quarterly (GDP/Debt WorldBank)                      │
│  Tier 4: Annual (Gini/COFER/Education/Military)              │
│  Tier 6: Centennial (JST Macrohistory R6 1870-2020)          │
├──────────────────────────────────────────────────────────────┤
│  ENGINE LAYER (20 modules)                                    │
│  ┌─ 8 Analysis Modules ──────────────────────────┐          │
│  │ Template · Cycle · Causal · Game · Stress      │          │
│  │ Narrative · System Dynamics · First Principles │          │
│  └────────────────────────────────────────────────┘          │
│  ┌─ V2 Upgrades ──────────────────────────────────┐         │
│  │ Sigmoid Feasibility · Trend-Aware Triggers     │          │
│  │ Continuous Phase Scoring · Momentum Tracking   │          │
│  └────────────────────────────────────────────────┘          │
│  ┌─ V3 Bayesian Layer ───────────────────────────┐          │
│  │ 8 Likelihood Functions · Log-Space Fusion      │          │
│  │ Shannon Entropy · Divergence Detection         │          │
│  └────────────────────────────────────────────────┘          │
│  ┌─ V3.1 Meta-Learning ──────────────────────────┐          │
│  │ Template Calibration · α[module][phase] Matrix │          │
│  │ Adaptive Weighting · Empirical Bayes           │          │
│  └────────────────────────────────────────────────┘          │
├──────────────────────────────────────────────────────────────┤
│  DASHBOARD (pure HTML/CSS/JS, Chart.js, Sentry dark theme)   │
│  6 tabs · 25+ charts · SVG causal chains · Scenario player   │
│  Bayesian confidence indicator · Mobile responsive           │
└──────────────────────────────────────────────────────────────┘
```

---

## Part 1: 数据管道设计

### 1.1 核心原则

1. **数据本地化** — SQLite 单文件，`.gitignore` 排除
2. **中国网络可达** — 新浪/东方财富为主，世界银行为辅
3. **API+Fallback 双轨** — 国际 API 不可靠，所有源都有回退值
4. **INSERT OR REPLACE** — 所有脚本幂等，可重复运行
5. **频率分级** — 日/月/季/年/百年各一套脚本

### 1.2 数据源映射

| 数据 | 来源 | 频率 | 跨度 | 注意事项 |
|------|------|------|------|---------|
| 美股实时 | `hq.sinajs.cn` | 日 | 当日 | GBK 编码，curl 后 decode |
| ETF 历史日线 | `stock.finance.sina.com.cn` US API | 日 | 2001+ | JSON 格式，字段 d/c |
| 中国宏观 | 东方财富 datacenter | 月 | 2000s+ | 部分数据需手动拼接 |
| 中美长序列 | World Bank API | 年 | 1960s+ | 需 fallback 表 |
| 百年数据 | JST Macrohistory R6 | 年 | 1870-2020 | Stata .dta 格式，学术许可 |
| GPR 地缘风险 | Caldara-Iacoviello 论文 | 月 | 1900-2026 | 学术文献手工录入+插值 |
| EPU 不确定性 | policyuncertainty.com | 月 | 1985-2026 | CSV header 列名不固定 |
| 政治极化 | V-Dem v13 | 年 | 1900-2023 | 大学生成数据 |

### 1.3 常见陷阱

- **GBK 编码**：新浪数据 `curl | python3` 失败 → `decode('gbk')`
- **ETF Symbol**：Sina K线用美股符号 (`spy`) 而非 `gb_spy`
- **World Bank 格式**：日期是 `YYYY` 需转 `YYYY-12-31`
- **单记录陷阱**：`china_real_rate` 只有 1 条 → 中国长债周期盲区
- **ETF 快照陷阱**：SPY 只有当日价格 → P0 必须补日线历史

---

## Part 2: 引擎设计

### 2.1 V2 升级模式

所有模块从 V1（硬编码阈值）→ V2（Sigmoid 连续函数）的模式：

```python
# V1: 硬编码
if cpi > 3.5: feasibility = 0.5
elif cpi > 2.5: feasibility = 0.7
else: feasibility = 0.9

# V2: Sigmoid 连续
feasibility = sigmoid(cpi, threshold=3.5, steepness=1.5, direction="below")
# cpi=2.4 → 84% feasible
# cpi=3.4 → 50% feasible
# cpi=4.4 → 17% feasible
```

**Steepness 参数指南：**
- 0.3-0.5: 极缓（结构指标如债务/GDP）
- 1.0-1.5: 中等（宏观指标如 CPI）
- 2.0-3.0: 锐利（金融指标如 VIX、曲线）

### 2.2 因果链设计

50 节点有向无环图，BFS 遍历：
- **触发条件**: OR 逻辑（非 AND — 否则收敛节点阻塞）
- **趋势感知**: 同时检查 5 日与 30 日均线方向
- **强度分数**: 0.15+（已触发）/ 0.03-0.15（逼近）

### 2.3 P1 校准结果

基于灵敏度分析，6 项阈值调整落地：

| 参数 | 旧值 | 新值 | 依据 |
|------|------|------|------|
| VIX 健康阈值 | 25 | 20 | 20 已是轻度紧张 |
| 黄金涨幅阈值 | 40% | 25% | +25% 即强去杠杆信号 |
| 中国债务警戒 | 300% | 250% | 国际红线标准 |
| 储备份额阈值 | 55% | 58% | 去美元化叙事启动点 |
| 曲线倒挂预警 | 0.88x | 0.95x | 平坦化即前置信号 |
| Fed 陡峭度 | 4.0 | 3.0 | 减少过度锐利跳变 |

**TOP 5 风险驱动力**: 利率曲线(±10) > VIX(±8) = 储备份额(±8) > 黄金(±6) > 债务(±5)

---

## Part 3: 贝叶斯三角验证 (V3)

### 3.1 为什么加权平均不够

```
传统:  score = (A + B + C) / 3         ← 零件求和
贝叶斯: P(phase | A,B,C) ∝ P(A|phase)×P(B|phase)×P(C|phase)×P(phase)  ← 信念更新
```

当模块一致时：加权平均=45分，贝叶斯=45±3分（高确信）
当模块分歧时：加权平均=45分，贝叶斯=45±22分（低确信 → 告警）

### 3.2 实现架构

```python
# Step 1: 每个模块输出条件概率分布
cycle_lik = {normal:0.05, bubble:0.22, crisis:0.22, delever:0.34, order:0.17}
causal_lik = {normal:0.02, bubble:0.10, crisis:0.40, delever:0.28, order:0.20}

# Step 2: Log-space 贝叶斯融合（数值稳定）
for phase in PHASES:
    log_p = log(prior[phase])
    for module_lik in likelihoods:
        log_p += alpha[module][phase] * log(module_lik[phase])
    posterior[phase] = exp(log_p - log_norm)

# Step 3: 输出
risk_score = Σ posterior[p] * risk_baseline[p]
confidence = f(entropy)  # high / medium / low / very_low
divergence = check_module_disagreement()
```

### 3.3 8 个似然函数设计

每个模块的 P(signal|phase) 映射逻辑：

| 模块 | 信号来源 | 映射逻辑 |
|------|---------|---------|
| 周期定位 | short/long/empire stage | 阶段 → 5 相乘法加权 |
| 因果推理 | trigger count + event domains | 事件类型 → 相关相放大 |
| 博弈论 | Fed/PBoC strategies + trajectory | 策略方向 → 相推断 |
| 压力测试 | n_alerts + top risks classification | 告警数 + 风险分类 |
| 叙事分析 | bull_ratio + tipping + divergence | 情绪极端 → 泡沫/危机 |
| 系统动力 | criticality + collapse_prob | 临界状态 → 危机放大 |
| 第一性原理 | chain activations | 链名匹配 → 相放大 |
| 历史模板 | similarity + crisis type | 危机类型 → 相映射 |

---

## Part 4: 元学习 (V3.1)

### 4.1 核心洞见

> 叙事模块在正常增长期最准 (α=0.50)，因果模块在危机期最准 (α=0.40)。让贝叶斯融合自动加权。

### 4.2 校准方法

```python
# 用 25 个历史模板作为"真相"标签
for template in HISTORICAL_TEMPLATES:
    true_phase = template.true_phase
    for module in MODULES:
        predicted = module.predict(features_at_date)
        confusion[module][predicted][true_phase] += 1

# 拉普拉斯平滑 → α 矩阵
alpha[module][phase] = (correct + 1) / (total_attempts + n_phases)
```

### 4.3 发现

| 模块 | 专长领域 | α 值 |
|------|---------|------|
| 叙事分析 | 正常增长 | 0.50 — 最好的「正常检测器」 |
| 系统动力 | 正常增长 | 0.50 |
| 第一性原理 | 正常增长 + 泡沫形成 | 0.50 / 0.38 |
| 因果推理 | 危机爆发 | 0.40 — 最好的「危机检测器」 |
| 周期定位 | 正常 + 秩序更替 | 0.38 / 0.33 |
| 压力测试 | 正常 + 秩序更替 | 0.38 / 0.33 |

### 4.4 A/B 效果

| 指标 | 无元学习 | 有元学习 | 变化 |
|------|---------|---------|------|
| 确信度 | medium | low | 更诚实地反映不确定性 |
| 泡沫概率 | 0.9% | 15.3% | 第一性原理检测到的信号被放大 |
| 危机概率 | 31.8% | 24.3% | 不可靠模块的危机信号被抑制 |

---

## Part 5: 看板设计

### 5.1 布局原则

> 决策层 → 证据层 → 审计层（从上到下）

1. **决策层**: 执行摘要 + 风险得分 + 确信度 + 仓位建议
2. **证据层**: 6 Tab 历史图表 + 因果链 SVG + 博弈终局
3. **审计层**: 交叉验证 + 背离检测 + 状态总览

### 5.2 技术决策

- Chart.js 4.4 + date-fns 适配器（时间轴必需）
- SVG 因果链用 `array.push()` 构建，防引用冲突
- `fitText()/fitLines()` 解决 CJK 字符宽度问题
- `serve_nocache.py` 强制 `Cache-Control: no-cache`
- `@media (max-width: 768px)` 移动端适配
- 场景推演：5 滑块 + 实时风险得分

### 5.3 SVG 因果链常见 Bug

1. **未闭合标签** → 整页空白 → `grep '<text[^>]*>[^<]*$'`
2. **反引号错位** → `` `</text>` `` 在 `${}` 前 → SyntaxError
3. **补丁吞行** → `patch` 工具可能吃掉相邻的 `DATA = JSON.parse(text)`
4. **AND→OR** → 收敛节点用 `any()` 而非 `all()`
5. **截断** → 移除所有 `[:8]` 硬编码切片

---

## Part 6: 部署与运维

### 6.1 快速启动

```bash
cd ~/macro-engine
# 首次设置
python3 data/fetchers/phase1_backfill.py
python3 data/fetchers/phase2_academic.py
python3 data/fetchers/phase3_jst.py
python3 data/fetchers/p0_gap_fill.py
python3 engine/meta_learning.py          # 校准可靠性矩阵

# 启动看板
cd dashboard && python3 serve_nocache.py 8502 &

# 每日更新
bash scripts/update_daily.sh
```

### 6.2 Cron 配置

```bash
# 通过 hermes cronjob 管理
cronjob create --prompt "更新每日宏观数据并导出" \
  --schedule "0 8 * * 1-5" --deliver local \
  --skills dalio-macro-framework stock-market-data
```

### 6.3 健康检查

```python
# 数据新鲜度
python3 -c "import sqlite3; db=sqlite3.connect('macro.db');
print(db.execute('SELECT indicator_name, MAX(date) FROM macro_indicators GROUP BY 1 ORDER BY 2 DESC LIMIT 10').fetchall())"

# 重新校准
python3 engine/meta_learning.py
```

---

## Part 7: 关键经验教训

### 做对了的

1. **SQLite 单文件** — 零运维，gitignored，clone 后本地生成
2. **纯静态看板** — 无后端依赖，浏览器即用
3. **幂等脚本** — INSERT OR REPLACE，可重复运行
4. **Sigmoid 连续化** — 消除离散跳变，平滑过渡
5. **贝叶斯融合** — 揭示模块分歧这个最有价值的信息
6. **元学习** — 系统自己学会谁更可信

### 踩过的坑

1. **加权平均抹平分歧** — 45 分看不出 6 个模块在打架
2. **AND 逻辑阻塞因果链** — 收敛节点卡死整条链
3. **单记录指标** — 1 条数据的引擎输出是噪音
4. **硬编码切片 `[:8]`** — 中国链被美链挤掉
5. **SVG 模板字面量反引号** — 一个字符崩全页
6. **补丁吞行** — `DATA = JSON.parse(text)` 被吃掉
7. **GBK 编码** — 新浪数据 silent fail

### 哲学

> "多视角不是用来求平均的，是用来交叉验证的。每个新视角更新你对真相的信念，而不是稀释它。" — 这就是贝叶斯三角验证的核心。

---

## 文件索引

```
macro-engine/
├── engine/
│   ├── orchestrator.py              # 总指挥 (Step1-6 + 贝叶斯)
│   ├── bayesian_orchestrator.py     # V3: 贝叶斯三角验证
│   ├── meta_learning.py             # V3.1: 元学习校准
│   ├── template_matcher.py          # 历史模板匹配
│   ├── cycle_locator.py             # 3周期定位
│   ├── causal_chain.py              # 50节点因果DAG
│   ├── game_theory_v2.py            # 博弈论 V2
│   ├── stress_test_v2.py            # 压力测试 V2
│   ├── narrative_v2.py              # 叙事分析 V2
│   ├── system_dynamics_v2.py        # 系统动力 V2
│   ├── first_principles.py          # 第一性原理
│   ├── historical_diff.py           # 历史差异分析
│   ├── divergence_detector.py       # 背离检测
│   └── p1_validation.py             # P1 回溯+灵敏度
├── data/fetchers/
│   ├── phase1_backfill.py           # Phase 1: 中美基础
│   ├── phase2_academic.py           # Phase 2: 学术数据
│   ├── phase3_jst.py                # Phase 3: 百年数据
│   ├── p0_gap_fill.py               # P0: 数据盲区补丁
│   ├── sina_v5.py                   # 新浪实时行情
│   ├── eastmoney_macro.py           # 东方财富宏观
│   └── worldbank.py                 # 世界银行 API
├── dashboard/
│   ├── index.html                   # 看板 (1686行)
│   ├── export_data.py               # DB→JSON 导出
│   └── serve_nocache.py             # HTTP 服务
├── reliability_matrix.json          # 元学习校准矩阵
├── macro.db                         # SQLite (gitignored)
└── README.md                        # 项目文档
```
