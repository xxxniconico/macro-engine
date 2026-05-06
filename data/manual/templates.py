"""播种历史模板 — Dalio 框架经典宏观时期。

每个模板 = 名称 + 国家 + 时期 + 12维特征向量 + 历史结果。
特征归一化参考: engine/template_matcher.py 中的 FEATURES 定义。

运行: python data/manual/templates.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.storage import save_template, get_all_templates, init_db

# ═══════════════════════════════════════════════════════════════
# 模板库
# 向量顺序: gdp_growth, inflation, pmi, debt_gdp, real_rate,
#            unemployment, equity_1y, gold_1y, policy_rate,
#            reserve_status, polarization, inequality
# 值域: [-1, 1] 归一化后
# ═══════════════════════════════════════════════════════════════

TEMPLATES = [
    {
        "name": "美国 1970s 滞胀",
        "country": "US",
        "period": "1974-1980",
        "vector": [
            -0.20,   # gdp: ~2% 低增长
             0.43,   # cpi: ~8% 高通胀
            -0.20,   # pmi: ~48 弱收缩
            -1.00,   # debt: ~35% 极低 ← 当时债务低
            -0.54,   # real_rate: ~-2% 深度负
            -0.33,   # unemployment: ~7%
            -0.20,   # equity: ~-10% 熊市
             0.50,   # gold: +30% 黄金牛市
             0.07,   # rates: ~8%
             1.00,   # reserve: ~70% 美元霸主
            -0.60,   # polarization: 50 较低
            -0.40,   # inequality: 0.36 较低
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],  # pmi 缺失 (有 ISM 但不用)
        "outcome": "Volcker 加息至 20% → 双底衰退 → 1982 年通胀受控 → 40 年大牛市前夜"
    },
    {
        "name": "美国 1982 Volcker 紧缩",
        "country": "US",
        "period": "1981-1982",
        "vector": [
            -0.30,   # gdp: ~-2% 衰退
             0.50,   # cpi: ~6% 仍高但回落中
            -0.30,   # pmi: ~45 深度收缩
            -0.70,   # debt: ~40% 低
             1.00,   # real_rate: ~7% 极高 ← 核心特征
             0.33,   # unemployment: ~10% 高
            -0.20,   # equity: ~-15% 熊市末段
            -0.20,   # gold: ~-5% 黄金回落
             1.00,   # rates: ~15% ← 历史峰值
             1.00,   # reserve: ~68% 高
            -0.50,   # polarization: 55
            -0.30,   # inequality: 0.37
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "通胀触顶回落 → 利率下行 → 1982-2000 大牛市 + 大缓和时代"
    },
    {
        "name": "日本 1990s 失落十年",
        "country": "JP",
        "period": "1990-2000",
        "vector": [
            -0.05,   # gdp: ~1% 极低增长
            -0.70,   # cpi: ~-1% 通缩
            -0.40,   # pmi: ~45 持续收缩
             0.35,   # debt: ~300% 极高 ← 政府债务/GDP
            -0.15,   # real_rate: ~1% 零利率
             0.33,   # unemployment: ~5% (日本定义偏高)
            -0.80,   # equity: ~-60% 股灾
            -0.50,   # gold: ~-15% 通缩环境
            -1.00,   # rates: ~0% 零利率
            -0.10,   # reserve: ~57% ↓
             0.20,   # polarization: 70 政局动荡
             0.00,   # inequality: 0.38
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "30 年通缩 + 零利率 → 失去的三十年 → 日经 2024 年才重回 1989 年高点"
    },
    {
        "name": "美国 2000 互联网泡沫",
        "country": "US",
        "period": "2000-2002",
        "vector": [
             0.05,   # gdp: ~2% 温和
             0.14,   # cpi: ~3% 温和
             0.00,   # pmi: ~48
            -0.60,   # debt: ~55% 低
             0.30,   # real_rate: ~3.5%
            -0.17,   # unemployment: ~5%
             0.90,   # equity: 先+30%后-40% ← 极端波动
            -0.30,   # gold: ~-5%
             0.00,   # rates: ~5.5%
             0.80,   # reserve: ~65%
            -0.10,   # polarization: 60
             0.40,   # inequality: 0.44 开始上升
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "纳指从 5000 跌至 1100 → 轻度衰退 → Fed 疯狂降息 → 催生房地产泡沫"
    },
    {
        "name": "美国 2008 全球金融危机",
        "country": "US",
        "period": "2008-2009",
        "vector": [
            -0.70,   # gdp: ~-4% 深度衰退
            -0.40,   # cpi: ~0% 通缩风险
            -0.80,   # pmi: ~35 崩溃
            -0.20,   # debt: ~100% 尚可控
             0.00,   # real_rate: ~0%
             0.83,   # unemployment: ~10% 高
            -0.80,   # equity: ~-50% 崩盘
             0.00,   # gold: ~0% (先跌后涨)
            -0.80,   # rates: ~0% 零利率
             0.20,   # reserve: ~62%↓
             0.60,   # polarization: 75 ← 茶党兴起
             0.60,   # inequality: 0.46 高
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "QE + 零利率 + 银行救助 → 缓慢复苏 → 民粹主义兴起 → 2016 年政治地震"
    },
    {
        "name": "欧元区 2012 债务危机",
        "country": "EU",
        "period": "2011-2013",
        "vector": [
            -0.40,   # gdp: ~-2%
             0.10,   # cpi: ~2.5%
            -0.40,   # pmi: ~45
             0.10,   # debt: ~200% (南欧平均)
             0.20,   # real_rate: ~2%
             0.50,   # unemployment: ~11% 南欧极高
            -0.20,   # equity: ~-20%
             0.10,   # gold: ~5%
            -0.60,   # rates: ~1%
             0.50,   # reserve: ~65% 欧元挑战
             0.00,   # polarization: 60
             0.40,   # inequality: 0.42
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "Draghi 'Whatever it takes' → OMT → 危机缓解 → 但南欧长期高失业 + 民粹"
    },
    {
        "name": "中国 2015 股灾",
        "country": "CN",
        "period": "2015-2016",
        "vector": [
             0.00,   # gdp: ~7% 但减速中
             0.00,   # cpi: ~2%
            -0.10,   # pmi: ~49 弱
             0.65,   # debt: ~340% 高 ← 地方债+企业债
            -0.20,   # real_rate: ~0%
            -0.20,   # unemployment: ~4%
             0.80,   # equity: 先+100% 后-45% 极端
            -0.30,   # gold: ~-10%
            -0.40,   # rates: ~2% (中国利率)
             0.30,   # reserve: ~63% ↓
            -0.20,   # polarization: 50
             0.20,   # inequality: 0.42
        ],
        "mask":    [1,1,1,1,1,1,1,1,1,1,1,1],
        "outcome": "国家队救市 + 去杠杆启动 → 2016-2017 年供给侧改革 → 2018 年贸易战新压力"
    },
    {
        "name": "亚洲 1997 金融危机",
        "country": "Asia",
        "period": "1997-1998",
        "vector": [
            -0.80,   # gdp: ~-7% 崩溃 (多国)
             0.00,   # cpi: ~5% 混合
            -0.60,   # pmi: ~40
             0.00,   # debt: ~180% 新兴市场
             1.00,   # real_rate: ~8% 为保汇率
             0.50,   # unemployment: ~8%
            -0.90,   # equity: ~-60%
            -0.20,   # gold: ~-10%
             0.60,   # rates: ~10% 高利率防御
            -0.20,   # reserve: ~60%
             0.00,   # polarization: 60
             0.20,   # inequality: 0.40
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "IMF 救助 + 紧缩 → 社会动荡 → 部分国家 5-10 年才恢复 → 教训：资本账户过快开放"
    },
    {
        "name": "美国 1929 大萧条",
        "country": "US",
        "period": "1929-1933",
        "vector": [
            -1.00,   # gdp: ~-15% 崩溃
            -0.70,   # cpi: ~-5% 深度通缩
            -1.00,   # pmi: ~30 灭绝
            -1.00,   # debt: ~30% (名义低但通缩致实际飙升)
            -0.30,   # real_rate: 通缩下实际极高
             1.00,   # unemployment: ~25% 历史峰值
            -1.00,   # equity: ~-85% 股灾
             1.00,   # gold: +70% (金本位脱钩后)
            -0.60,   # rates: ~3% (名义低)
             1.00,   # reserve: ~70%
             0.40,   # polarization: 70 激进政治
             0.40,   # inequality: 0.45 高
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "新政 + WWII 动员 → 最终走出 → 催生 Bretton Woods → 美国霸权巅峰前夜"
    },
    {
        "name": "美国 2020 COVID 冲击",
        "country": "US",
        "period": "2020",
        "vector": [
            -1.00,   # gdp: ~-10% 骤停
            -0.50,   # cpi: ~0% 瞬间通缩
            -0.80,   # pmi: ~38 骤停
             0.20,   # debt: ~200% 快速上升
            -0.80,   # real_rate: ~-3%
             1.00,   # unemployment: ~15% 骤升
            -0.20,   # equity: ~-30% 然后 V 型
             0.50,   # gold: +25% 避险
            -1.00,   # rates: ~0%
             0.00,   # reserve: ~60%↓ 加速
             0.80,   # polarization: 85 极分化
             0.80,   # inequality: 0.48 K 型复苏
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "史诗级财政+货币刺激 → 2021 通胀爆发 → 2022 Fed 激进加息 → 2023 银行危机"
    },
    {
        "name": "美国 2006 房地产泡沫顶峰",
        "country": "US",
        "period": "2006-2007",
        "vector": [
             0.00,   # gdp: ~2% 正常
             0.20,   # cpi: ~3.5%
             0.00,   # pmi: ~50
            -0.30,   # debt: ~80% 私债高
             0.40,   # real_rate: ~3%
            -0.40,   # unemployment: ~4.5% 极低
             0.10,   # equity: ~10% 还在涨
             0.00,   # gold: ~0%
             0.30,   # rates: ~5.25%
             0.40,   # reserve: ~63%
             0.30,   # polarization: 68
             0.50,   # inequality: 0.45
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "次贷危机 → 2008 GFC → 大衰退 → 这是'暴风雨前的平静'的经典案例"
    },
    {
        "name": "英国 1976 IMF 危机",
        "country": "UK",
        "period": "1976",
        "vector": [
            -0.10,   # gdp: ~0%
             0.70,   # cpi: ~25% 恶性通胀
            -0.50,   # pmi: ~42
            -0.70,   # debt: ~50% 低
            -1.00,   # real_rate: ~-10% 深度负
             0.00,   # unemployment: ~5%
            -0.10,   # equity: ~-15%
             0.80,   # gold: +40%
             0.60,   # rates: ~12%
             0.50,   # reserve: ~66%↓
            -0.40,   # polarization: 55
            -0.20,   # inequality: 0.35
        ],
        "mask":    [1,1,0,1,1,1,1,1,1,1,1,1],
        "outcome": "英镑危机 → IMF 贷款 + 紧缩条件 → 1979 撒切尔上台 → 大刀阔斧改革"
    },
]


def seed():
    """播种所有模板到数据库。"""
    init_db()

    existing = {t["name"] for t in get_all_templates()}
    added, updated, skipped = 0, 0, 0

    for t in TEMPLATES:
        if t["name"] in existing:
            updated += 1
        else:
            added += 1

        save_template(
            name=t["name"],
            country=t["country"],
            period=t["period"],
            vector={
                "values": t["vector"],
                "mask": t.get("mask", [1]*12),
                "feature_names": [
                    "gdp_growth","inflation","pmi","debt_gdp","real_rate",
                    "unemployment","equity_1y","gold_1y","policy_rate",
                    "reserve_status","polarization","inequality"
                ],
            },
            outcome=t["outcome"]
        )

    print(f"✅ 模板播种完成: 新增 {added}, 更新 {updated}, 总计 {added+updated}")
    print(f"   现有模板: {len(get_all_templates())}")


if __name__ == "__main__":
    seed()
