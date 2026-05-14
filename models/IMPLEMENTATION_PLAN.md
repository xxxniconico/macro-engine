# BQAS 模型实施计划

> **版本**: v1.0  
> **日期**: 2026-05-08  
> **基于**: [quant_buffett_design.md](research/quant_buffett_design.md) 研究文档  
> **总任务数**: 5  
> **预计总工时**: 15–25 分钟（每任务 3–5 分钟）

---

## 项目结构总览

```
macro-engine/models/
├── research/
│   └── quant_buffett_design.md      # 研究文档（已完成）
├── value_investor.py                # 旧版 B-Score 单票评分器（保留不动）
│
│   # ↓ 以下为本次实施的新文件 ↓
├── IMPLEMENTATION_PLAN.md           # 本文件
├── data_fetcher.py                  # 任务1: 数据获取层
├── factor_engine.py                 # 任务2: 一票否决 + 九因子计算
├── bqas_model.py                    # 任务3: 综合打分与选股
├── backtest_bqas.py                 # 任务4: 回测框架
└── run_bqas.py                      # 任务5: CLI入口 + 端到端集成
```

---

## 任务间接口定义（核心数据格式）

所有任务共享以下标准化 DataFrame 列名。任务1产出此格式，任务2/3/4消费此格式。

### `universe` DataFrame（全市场股票基本面数据）

每行 = 一只股票，列如下：

```
# --- 标识 ---
code           str     # 股票代码，如 '600519'
name           str     # 股票名称，如 '贵州茅台'
industry       str     # 行业分类，如 '食品饮料'、'银行'

# --- 行情数据 ---
market_cap     float   # 总市值（亿元）
pb             float   # 市净率
pe             float   # 市盈率 TTM
daily_volume   float   # 日均成交额（万元）

# --- 近5年财务数据（index 0=最近一年, index 4=5年前）---
roe_5y         list[float]  # 5年ROE，如 [0.22, 0.20, 0.19, 0.18, 0.17]
gross_margin_5y list[float] # 5年毛利率，如 [0.45, 0.43, 0.42, 0.40, 0.38]
net_income_5y  list[float]  # 5年净利润（亿元）
ocf_5y         list[float]  # 5年经营活动现金流净额（亿元）
op_profit_5y   list[float]  # 5年营业利润（亿元）
interest_exp_5y list[float] # 5年利息支出（亿元）
depreciation_5y list[float] # 5年折旧摊销（亿元）
capex_5y       list[float]  # 5年购建固定资产支出（亿元）
total_assets_5y list[float] # 5年总资产（亿元）
total_liab_5y  list[float]  # 5年总负债（亿元）
current_assets_5y list[float]
current_liab_5y  list[float]
cash_5y        list[float]  # 5年现金及等价物（亿元）
lt_invest_5y   list[float]  # 5年长期股权投资（亿元）
goodwill_5y    list[float]  # 5年商誉（亿元）
equity_5y      list[float]  # 5年股东权益（亿元）
revenue_5y     list[float]  # 5年营业收入（亿元）

# --- 一票否决相关字段 ---
is_st          bool      # 是否 ST/*ST
audit_opinion  str       # 审计意见: 'standard' / 'non_standard' / 'unknown'
listing_date   str       # 上市日期 YYYY-MM-DD
penalty_flag   bool      # 5年内是否有证监会处罚(财务类)
pledge_ratio   float     # 大股东质押比例

# --- 行业分位数（任务1预计算，任务3使用）---
gm_percentile  float     # 毛利率在全市场的分位数 [0, 1]
pb_industry_median float  # 同行业PB中位数
da_industry_median float  # 同行业资产负债率中位数
```

### `factor_scores` DataFrame（任务2产出 → 任务3消费）

```
code           str
Q1_ROE         float   # 0-10
Q2_GM          float   # 0-10
Q3_CFO         float   # 0-10
Q4_Accrual     float   # 0-10
V1_EV_OpE      float   # 0-10
V2_FCF_Yield   float   # 0-10
V3_PB          float   # 0-10
H1_IC          float   # 0-10
H2_Debt        float   # 0-10
H3_Current     float   # 0-10
is_rejected    bool    # 是否被一票否决
reject_reason  str     # 否决原因
```

### `holdings` DataFrame（任务3产出 → 任务4消费）

```
code           str
name           str
total_score    float   # 综合得分 0-10
q_score        float
v_score        float
h_score        float
weight         float   # 持仓权重
```

---

## 任务 1：数据获取层

| 属性 | 值 |
|------|-----|
| **编号** | T1 |
| **名称** | 数据获取层 — 从 akshare 拉取并标准化 |
| **负责文件** | `data_fetcher.py` |
| **前置依赖** | 无（需安装 akshare: `pip install akshare pandas numpy`） |
| **预计工时** | 4–5 分钟 |

### 详细指令

创建一个文件 `models/data_fetcher.py`，实现以下内容：

1. **`fetch_stock_list()`** — 用 `akshare.stock_zh_a_spot_em()` 获取全A股列表，返回 DataFrame，列包含：
   - `code`: 股票代码（6位字符串，如 `'600519'`）
   - `name`: 股票名称
   - `market_cap`: 总市值（原始单位：元 → 转换为亿元）
   - `pb`: 市净率
   - `pe`: 市盈率

2. **`fetch_financial_data(code)`** — 用 `akshare.stock_financial_abstract_ths(code)` 或其他可用接口获取单只股票的近年财报，返回 dict：
   - roe（直接取ROE指标）、gross_margin、net_income、ocf 等（见上方 `universe` DataFrame 列定义）
   - 取最近5年数据，index 0 为最近年份
   - **容错处理**：任一数据缺失 → 填 `np.nan`

3. **`build_universe(codes, industry_map)`** — 批量调用 `fetch_financial_data`，构建完整 `universe` DataFrame
   - 添加行业映射（可先用简单映射，如 `industry_map = {'600519': '食品饮料', ...}`）
   - 计算 `gm_percentile`（毛利率的全市场分位数）
   - 计算 `pb_industry_median` 和 `da_industry_median`
   - ST 状态、审计意见等先默认为安全值（后续可优化）

4. **`save_universe(df, path)`** / **`load_universe(path)`** — 序列化为 Parquet，避免重复拉取

### 验收标准

```python
# 测试：获取单只股票数据
from models.data_fetcher import fetch_financial_data
d = fetch_financial_data('600519')     # 贵州茅台
assert 'roe_5y' in d
assert len(d['roe_5y']) >= 3           # 至少有3年数据
assert all(isinstance(x, (int, float)) for x in d['roe_5y'])

# 测试：构建 universe（小样本）
from models.data_fetcher import build_universe
df = build_universe(['600519', '000858', '000333'], {})
assert len(df) == 3
assert 'gm_percentile' in df.columns
print("✅ 任务1通过: 数据获取层正常")
```

---

## 任务 2：一票否决 + 九因子计算

| 属性 | 值 |
|------|-----|
| **编号** | T2 |
| **名称** | 因子计算引擎 — 硬过滤器 + 九因子评分 |
| **负责文件** | `factor_engine.py` |
| **前置依赖** | 任务1（需 `universe` DataFrame 格式） |
| **预计工时** | 4–5 分钟 |

### 详细指令

创建文件 `models/factor_engine.py`，实现两个核心模块：

#### 模块A：一票否决（`hard_filter(row) -> (bool, str)`）

逐行检查 `universe` 中的 9 项条件，任一项触发即返回 `(True, 原因)`：

```python
def hard_filter(row: dict) -> tuple:
    """
    返回 (is_rejected: bool, reason: str)
    检查以下 9 项：
    1. ST/*ST → row['is_st'] == True
    2. 非标审计 → row['audit_opinion'] != 'standard'
    3. 近3年连续净利润为负 → all(ni < 0 for ni in row['net_income_5y'][:3])
    4. 近3年OCF均 < 0 → all(ocf < 0 for ocf in row['ocf_5y'][:3])
    5. 市值 < 30亿 或 日均成交 < 2000万 → row['market_cap'] < 30 or row['daily_volume'] < 2000
    6. 上市不满3年 → (today - listing_date).days < 1095
    7. 有财务类处罚 → row['penalty_flag'] == True
    8. 商誉/净资产 > 50% 且 商誉 > 10亿 → goodwill/equity > 0.5 and goodwill > 10
    9. 大股东质押 > 70% → row['pledge_ratio'] > 0.7
    """
```

#### 模块B：九因子打分（每个因子独立函数，输入 row dict → 输出 0–10 分）

严格按照研究文档 4.2 节的公式：

| 因子 | 函数名 | 公式 |
|------|--------|------|
| Q1_ROE | `calc_Q1_ROE(row)` | `min(mean(roe_5y), 0.30) / 0.30 * 10` |
| Q2_GM | `calc_Q2_GM(row)` | `1 + 9 * gm_percentile` |
| Q3_CFO | `calc_Q3_CFO(row)` | `min(mean(ocf_5y[:3])/mean(net_income_5y[:3]), 2.0) / 2.0 * 10`（净利润均值>0时才计算，否则0分） |
| Q4_Accrual | `calc_Q4_Accrual(row)` | `max(0, 1 - abs(ni-ocf)/ta / 0.15) * 10` |
| V1_EV_OpE | `calc_V1_EV_OpE(row)` | 计算 EV = market_cap + total_liab - cash - lt_invest*0.5; OpEarnings = op_profit + depreciation + interest_exp; 得分 = `max(0, (15 - min(EV/OpEarnings, 15)) / 15 * 10)` |
| V2_FCF_Yield | `calc_V2_FCF_Yield(row)` | FCF = ocf - capex; Yield = FCF / market_cap; 得分 = `min(max(Yield, 0), 0.15) / 0.15 * 10` |
| V3_PB | `calc_V3_PB(row)` | `max(0, 1 - pb/pb_industry_median) * 10`（确保 pb > 0） |
| H1_IC | `calc_H1_IC(row)` | `min((op_profit + interest_exp) / interest_exp, 20) / 20 * 10`（利息支出>0时） |
| H2_Debt | `calc_H2_Debt(row)` | `max(0, 1 - (total_liab/total_assets)/0.70) * 10` |
| H3_Current | `calc_H3_Current(row)` | `min(current_assets/current_liab, 3.0) / 3.0 * 10` |

#### 主函数

```python
def calculate_all_factors(universe_df: pd.DataFrame) -> pd.DataFrame:
    """
    输入: universe DataFrame（任务1产出格式）
    输出: factor_scores DataFrame
    - 先跑 hard_filter，被否决的标记 is_rejected=True
    - 对通过的股票计算全部9个因子
    - 被否决股票的因子分全部填 0
    """
```

### 验收标准

```python
from models.data_fetcher import build_universe
from models.factor_engine import calculate_all_factors, hard_filter

# 构建小样本
df = build_universe(['600519', '000858', '000333'], {})

# 测试一票否决
row = df.iloc[0].to_dict()
rejected, reason = hard_filter(row)
print(f"否决检查: rejected={rejected}, reason={reason}")

# 测试全量因子计算
scores = calculate_all_factors(df)
assert list(scores.columns) == ['code', 'Q1_ROE', 'Q2_GM', 'Q3_CFO', 'Q4_Accrual',
    'V1_EV_OpE', 'V2_FCF_Yield', 'V3_PB', 'H1_IC', 'H2_Debt', 'H3_Current',
    'is_rejected', 'reject_reason']
# 验证得分在 0-10 范围
for col in ['Q1_ROE', 'Q2_GM', 'Q3_CFO']:
    assert scores[col].between(0, 10).all(), f"{col} 得分超出 0-10"
print("✅ 任务2通过: 一票否决 + 九因子计算正常")
```

---

## 任务 3：综合打分与选股

| 属性 | 值 |
|------|-----|
| **编号** | T3 |
| **名称** | BQAS 综合模型 — 加权、行业调整、排名选股 |
| **负责文件** | `bqas_model.py` |
| **前置依赖** | 任务1（数据格式）、任务2（因子得分） |
| **预计工时** | 3–4 分钟 |

### 详细指令

创建文件 `models/bqas_model.py`，实现 `BQASModel` 类：

```python
class BQASModel:
    """
    巴菲特量化评估系统主模型
    
    三维度九因子加权打分 → 排序 → Top N 选股
    """
    
    # 默认权重（研究文档 4.1 节）
    DEFAULT_WEIGHTS = {
        'Q1_ROE': 0.12, 'Q2_GM': 0.10, 'Q3_CFO': 0.10, 'Q4_Accrual': 0.08,
        'V1_EV_OpE': 0.15, 'V2_FCF_Yield': 0.12, 'V3_PB': 0.08,
        'H1_IC': 0.10, 'H2_Debt': 0.08, 'H3_Current': 0.07,
    }
    
    # 行业特殊处理矩阵（研究文档 4.5 节）
    INDUSTRY_ADJUSTMENTS = {
        '银行': {'V3_PB': 0.15, 'V1_EV_OpE': 0.08, 'H2_Debt': 0.00, 'H1_IC': 0.15},
        '保险': {'V3_PB': 0.15, 'V1_EV_OpE': 0.08, 'H2_Debt': 0.00, 'H1_IC': 0.15},
        '券商': {'V3_PB': 0.15, 'V1_EV_OpE': 0.08, 'H2_Debt': 0.00, 'H1_IC': 0.15},
        '房地产': {'H2_Debt': 0.00, 'H1_IC': 0.13, 'H3_Current': 0.12},
        '互联网': {'V3_PB': 0.04, 'V1_EV_OpE': 0.19},
        '软件': {'V3_PB': 0.04, 'V1_EV_OpE': 0.19},
    }
    
    def __init__(self, weights=None, industry_adjustments=None, top_n=30):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.industry_adjustments = industry_adjustments or self.INDUSTRY_ADJUSTMENTS
        self.top_n = top_n
    
    def apply_industry_weights(self, industry: str) -> dict:
        """根据行业调整权重，返回调整后的权重字典"""
    
    def score_universe(self, factor_scores: pd.DataFrame, 
                       universe_df: pd.DataFrame) -> pd.DataFrame:
        """
        输入: factor_scores (任务2产出) + universe_df (获取行业信息)
        输出: holdings DataFrame（含 total_score, q_score, v_score, h_score, weight）
        步骤:
          1. 剔除 is_rejected=True 的股票
          2. 对每只股票根据行业调整权重
          3. 计算三个维度得分和总分
          4. 按 total_score 降序排列
          5. 取 top_n 只，等权分配 weight = 1/top_n
        """
    
    def rebalance(self, factor_scores: pd.DataFrame, 
                  universe_df: pd.DataFrame) -> pd.DataFrame:
        """季度再平衡入口，内部调用 score_universe"""
```

**关键实现细节**：
- 权重调整后，H2_Debt 被置零时，必须确保该维度的其他因子权重总和仍为 25%（文档 4.5 节：银行 H2 权重分配给 H1）
- 金融行业：H2_Debt（资产负债率）不适用，其权重按文档 4.5 节重新分配
- 最终总分范围 [0, 10]，等权持仓 weight = `1 / top_n`

### 验收标准

```python
from models.bqas_model import BQASModel
import pandas as pd

# 构造模拟 factor_scores
scores = pd.DataFrame({
    'code': ['A', 'B', 'C'],
    'Q1_ROE': [9, 5, 2], 'Q2_GM': [8, 6, 3], 'Q3_CFO': [7, 7, 4], 'Q4_Accrual': [6, 5, 2],
    'V1_EV_OpE': [9, 4, 1], 'V2_FCF_Yield': [8, 5, 2], 'V3_PB': [7, 6, 3],
    'H1_IC': [10, 5, 1], 'H2_Debt': [8, 6, 2], 'H3_Current': [7, 5, 3],
    'is_rejected': [False, False, False], 'reject_reason': ['', '', '']
})
universe = pd.DataFrame({
    'code': ['A', 'B', 'C'],
    'industry': ['食品饮料', '银行', '制造业']
})

model = BQASModel(top_n=2)
holdings = model.score_universe(scores, universe)

assert len(holdings) == 2      # top_n=2
assert 'total_score' in holdings.columns
assert 'weight' in holdings.columns
assert abs(holdings['weight'].sum() - 1.0) < 0.01  # 权重和为1
assert holdings.iloc[0]['total_score'] >= holdings.iloc[1]['total_score']  # 降序

# 验证银行行业权重调整
w = model.apply_industry_weights('银行')
assert w['H2_Debt'] == 0.0
assert w['V3_PB'] == 0.15
print("✅ 任务3通过: 综合打分与选股正常")
```

---

## 任务 4：回测框架

| 属性 | 值 |
|------|-----|
| **编号** | T4 |
| **名称** | 回测框架 — 季度再平衡 + 绩效指标 |
| **负责文件** | `backtest_bqas.py` |
| **前置依赖** | 任务1（数据加载）、任务3（BQASModel） |
| **预计工时** | 4–5 分钟 |

### 详细指令

创建文件 `models/backtest_bqas.py`，实现 `BQASBacktest` 类：

```python
class BQASBacktest:
    """
    BQAS 模型回测器
    
    参数:
      model: BQASModel 实例
      universe_df: 全时段 universe DataFrame（含日期列 'date'）
      price_df: 股票日频价格 DataFrame，columns=股票代码, index=日期
      benchmark_code: 基准代码，如 '000300'（沪深300）
      start_date: 回测起始日期 '2010-01-01'
      end_date: 回测结束日期 '2025-12-31'
      cost_rate: 单边交易成本 0.0015（0.15%）
    """
    
    def __init__(self, model, universe_df, price_df, 
                 benchmark_code='000300', start_date='2010-01-01',
                 end_date='2025-12-31', cost_rate=0.0015):
        ...
    
    def get_rebalance_dates(self) -> list:
        """生成季度再平衡日期：每年 4/30, 8/31, 10/31（财报截止日后）"""
    
    def run(self) -> dict:
        """
        主回测循环：
        for each quarter:
          1. 取该时点的 universe 切片（as_of 该季度）
          2. 调用 factor_engine.calculate_all_factors()
          3. 调用 model.rebalance() 获取持仓
          4. 模拟持有到下个季度（用 price_df 计算区间收益）
          5. 扣除换仓的交易成本
        返回 metrics 字典
        """
    
    def calc_metrics(self, portfolio_returns, benchmark_returns) -> dict:
        """
        计算以下指标（均年化）：
        - annual_return: 年化收益率
        - annual_excess: 年化超额收益（vs 基准）
        - annual_volatility: 年化波动率
        - sharpe_ratio: 夏普比率（无风险利率取 2.5%）
        - max_drawdown: 最大回撤
        - information_ratio: 信息比率
        - win_rate: 年度胜率（跑赢基准的年数/总年数）
        - turnover: 年均单边换手率
        """
```

**实现重点**：
- 季度再平衡日期：用 4/30、8/31、10/31（年报/中报/三季报截止后）
- 回测循环用 `for` 而非向量化（简单可读）
- 基准收益从 `price_df[benchmark_code]` 获取，若无则用简单等权全市场
- 输出 metrics 要同时打印到 stdout

**回测指标标准**（研究文档 3.2 节）：

| 指标 | 优秀 | 合格 |
|------|------|------|
| 年化超额 | > 8% | > 4% |
| 夏普比率 | > 0.6 | > 0.35 |
| 信息比率 | > 0.8 | > 0.4 |
| 最大回撤 | < 35% | < 50% |

### 验收标准

```python
from models.backtest_bqas import BQASBacktest
from models.bqas_model import BQASModel
from models.factor_engine import calculate_all_factors
import pandas as pd
import numpy as np

# 构造模拟数据（100只股票，3年日数据）
np.random.seed(42)
codes = [f'{i:06d}' for i in range(100)]
dates = pd.date_range('2022-01-01', '2024-12-31', freq='B')
price_df = pd.DataFrame(
    np.random.lognormal(0.0003, 0.02, (len(dates), len(codes))).cumprod(axis=0),
    index=dates, columns=codes
)
price_df['000300'] = np.random.lognormal(0.0002, 0.015, len(dates)).cumprod()

# 简化 universe
universe = pd.DataFrame({
    'code': codes,
    'industry': ['制造业'] * 100,
    'date': '2022-01-01',
    # ... 其他必要列填默认值
})

model = BQASModel(top_n=20)
bt = BQASBacktest(model, universe, price_df, start_date='2022-01-01', end_date='2024-12-31')
metrics = bt.run()

assert 'sharpe_ratio' in metrics
assert 'max_drawdown' in metrics
assert 'annual_return' in metrics
print(f"年化收益: {metrics['annual_return']:.2%}, 夏普: {metrics['sharpe_ratio']:.2f}")
print("✅ 任务4通过: 回测框架正常")
```

---

## 任务 5：CLI 入口 + 端到端集成

| 属性 | 值 |
|------|-----|
| **编号** | T5 |
| **名称** | 运行脚本 — CLI 入口 + 报告输出 |
| **负责文件** | `run_bqas.py` |
| **前置依赖** | 任务1–4（所有模块） |
| **预计工时** | 3–4 分钟 |

### 详细指令

创建文件 `run_bqas.py`，实现 CLI 入口脚本：

```python
"""
BQAS 巴菲特量化评估系统 — CLI 入口

用法:
  # 拉取数据并缓存
  python -m models.run_bqas fetch --output models/data/universe.parquet
  
  # 打分筛选（从缓存读取）
  python -m models.run_bqas score --input models/data/universe.parquet
  
  # 完整回测
  python -m models.run_bqas backtest --input models/data/universe.parquet --start 2018-01-01 --end 2025-12-31
  
  # 一键运行全流程
  python -m models.run_bqas all --top 30 --start 2018-01-01
"""

import argparse
import sys
from pathlib import Path

def cmd_fetch(args):
    """拉取数据：从 akshare 获取全A股数据并缓存"""
    from models.data_fetcher import build_universe, save_universe
    # 先用小样本（前50只）快速验证，完整拉取需较长时间
    print("🚀 拉取全A股数据...")
    # ...

def cmd_score(args):
    """打分：读缓存 → 一票否决 → 九因子 → 综合排名"""
    from models.data_fetcher import load_universe
    from models.factor_engine import calculate_all_factors
    from models.bqas_model import BQASModel
    print("📊 执行 BQAS 打分...")
    # ...

def cmd_backtest(args):
    """回测：完整回测流程"""
    from models.data_fetcher import load_universe
    from models.factor_engine import calculate_all_factors
    from models.bqas_model import BQASModel
    from models.backtest_bqas import BQASBacktest
    print("📈 执行回测...")
    # ...

def cmd_all(args):
    """一键全流程"""
    cmd_fetch(args)
    cmd_score(args)
    cmd_backtest(args)

def main():
    parser = argparse.ArgumentParser(description='BQAS 巴菲特量化评估系统')
    subparsers = parser.add_subparsers(dest='command')
    
    p_fetch = subparsers.add_parser('fetch', help='拉取数据')
    p_fetch.add_argument('--output', default='models/data/universe.parquet')
    p_fetch.add_argument('--limit', type=int, default=50, help='拉取股票数量(测试用)')
    
    p_score = subparsers.add_parser('score', help='打分筛选')
    p_score.add_argument('--input', default='models/data/universe.parquet')
    p_score.add_argument('--top', type=int, default=30)
    
    p_backtest = subparsers.add_parser('backtest', help='回测')
    p_backtest.add_argument('--input', default='models/data/universe.parquet')
    p_backtest.add_argument('--start', default='2018-01-01')
    p_backtest.add_argument('--end', default='2025-12-31')
    p_backtest.add_argument('--top', type=int, default=30)
    
    p_all = subparsers.add_parser('all', help='一键全流程')
    p_all.add_argument('--output', default='models/data/universe.parquet')
    p_all.add_argument('--limit', type=int, default=50)
    p_all.add_argument('--top', type=int, default=30)
    p_all.add_argument('--start', default='2018-01-01')
    p_all.add_argument('--end', default='2025-12-31')
    
    args = parser.parse_args()
    if args.command == 'fetch':
        cmd_fetch(args)
    elif args.command == 'score':
        cmd_score(args)
    elif args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'all':
        cmd_all(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
```

**输出格式**（`cmd_score` 和 `cmd_backtest` 的结果）：

```
═══════════════════════════════════════════════════════
  BQAS 巴菲特量化评估系统 v1.0
═══════════════════════════════════════════════════════

📊 全市场扫描结果
  候选池: 2847 只 (剔除 ST/非标/亏损等: 213 只)
  综合打分 Top 30:
  
  排名  代码      名称        总分   质量   估值   健康
  ─────────────────────────────────────────────────
  1    600519   贵州茅台    8.45   3.52  2.91  2.02
  2    000858   五粮液      8.12   3.38  2.85  1.89
  ...

📈 回测绩效 (2018-01-01 ~ 2025-12-31)
  年化收益:   12.3%  (基准沪深300: 4.2%)
  年化超额:   +8.1%
  夏普比率:   0.62
  最大回撤:   -28.5%
  信息比率:   0.78
  年度胜率:   75% (6/8年)
  年均换手:   120%
```

### 验收标准

```bash
# 完整流程测试（小样本，快速验证）
cd /home/xxxsuli/macro-engine
python -m models.run_bqas all --limit 20 --top 10 --start 2022-01-01 --end 2024-12-31

# 预期输出:
# ✅ 数据拉取完成 (20只)
# ✅ 因子计算完成
# ✅ 选股完成 (Top 10)
# ✅ 回测完成
# 并打印格式化报告
```

---

## 任务依赖图

```
T1 (data_fetcher.py)     ← 无依赖，最先做
    ↓
T2 (factor_engine.py)    ← 依赖 T1 的数据格式
    ↓
T3 (bqas_model.py)       ← 依赖 T2 的因子得分格式
    ↓
T4 (backtest_bqas.py)    ← 依赖 T1 + T2 + T3
    ↓
T5 (run_bqas.py)         ← 依赖 T1–T4，串接所有模块
```

---

## 附录A：检查清单

实施完成后逐项验证：

- [ ] 9 个因子全部实现：Q1 ROE, Q2 GM, Q3 CFO, Q4 Accrual, V1 EV/OpE, V2 FCF Yield, V3 PB, H1 IC, H2 Debt, H3 Current
- [ ] 9 项一票否决全部实现（ST、非标审计、连续亏损、OCF为负、市值<30亿、上市<3年、处罚、商誉风险、质押风险）
- [ ] 行业特殊处理：银行/保险/券商（PB权重15%、H2不适用）、地产（H2不适用）、互联网/软件（PB权重4%）
- [ ] 周期股平滑处理：V1 用5年中位数、Q1 用5年中位数
- [ ] 数据获取层独立可测（用单只股票验证）
- [ ] 因子计算层独立可测（用构造数据验证得分范围 0-10）
- [ ] 综合打分权重和为 1.0（含行业调整后各维度权重不变：Q=0.40, V=0.35, H=0.25）
- [ ] 回测框架可跑通（模拟数据或真实数据）
- [ ] CLI 四个子命令均可正常执行

---

## 附录B：已知风险与缓解

| 风险 | 说明 | 缓解 |
|------|------|------|
| akshare 接口不稳定 | 东方财富 API 可能限流或改版 | 任务1增加重试 + 缓存 Parquet |
| 财报数据缺失 | 部分股票缺少5年完整数据 | 容错处理，缺失填 nan，打分时跳过 |
| 行业分类不准确 | 无 Wind/申万行业分类 | 先用简单映射，后续可接 akshare 行业分类接口 |
| 回测速度慢 | 全市场5000+股票 × 15年 | 先用小样本验证逻辑，后续可向量化优化 |

---

*实施计划结束 — 版本 v1.0*
