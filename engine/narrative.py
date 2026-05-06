"""叙事分析引擎 — Dalio 框架的叙事追踪视角。

核心理念：市场由叙事驱动。叙事 → 资金流 → 价格 → 验证叙事 → 强化。
最危险的时刻：当所有人都相信一个叙事时，往往就是反转的前夜。

追踪维度：
1. 主流叙事主题（当前市场在讲什么故事）
2. 叙事强度/共识度
3. 叙事转折点信号
4. 叙事与数据的背离度
"""

import sys
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot


# ═══════════════════════════════════════════════════════
#  主流叙事库 — 根据当前宏观环境动态匹配
#  每个叙事 = 主题 + 触发条件 + 强度信号 + 风险
# ═══════════════════════════════════════════════════════

NARRATIVES = [
    {
        "theme": "去美元化加速",
        "alias": "De-dollarization",
        "triggers": ["usd_reserve_share < 58", "gold > 4500", "em_eem > 65"],
        "strength_signals": ["gold", "em_eem", "usd_reserve_share"],
        "risk": "positive" if False else "warning",  # 动态判断
        "description": "全球央行购金潮+BRICS结算去美元 → 储备货币体系多极化",
        "peak_signal": "当CNBC/Fox/Bloomberg头版全是去美元化时 → 接近反转",
        "contra_narrative": "美元仍无替代品，去美元化是伪命题",
    },
    {
        "theme": "滞胀幽灵回归",
        "alias": "Stagflation Returns",
        "triggers": ["us_cpi > 3", "us_unemployment > 5", "us_yield_curve < 0.90"],
        "strength_signals": ["us_cpi", "us_unemployment", "us_vixy"],
        "risk": "warning",
        "description": "通胀顽固+增长放缓+央行两难 → 1970s重现",
        "peak_signal": "当Fed承认'暂时性'通胀是永久性 → 叙事全面确立",
        "contra_narrative": "AI生产力革命将压制通胀，这是过渡期",
    },
    {
        "theme": "软着陆叙事",
        "alias": "Soft Landing",
        "triggers": ["china_pmi > 50", "us_unemployment < 4.5", "us_cpi < 3"],
        "strength_signals": ["china_pmi", "us_unemployment", "us_cpi", "us_sp500"],
        "risk": "positive",
        "description": "Fed成功控通胀不引发衰退 → 完美软着陆",
        "peak_signal": "当华尔街一致预期软着陆 → 市场已price in一切好事",
        "contra_narrative": "软着陆是预期管理，数据显示的是硬着陆前兆",
    },
    {
        "theme": "中国日本化",
        "alias": "China Japanification",
        "triggers": ["china_debt_gdp > 280", "china_cpi < 1", "china_pmi < 50"],
        "strength_signals": ["china_debt_gdp", "china_cpi", "china_pmi"],
        "risk": "warning",
        "description": "高债务+通缩压力+人口下降 → 中国走向日本失落三十年",
        "peak_signal": "当国内自媒体集体唱衰 → 政策反转信号",
        "contra_narrative": "中国有更强的政策工具+产业升级空间，不会日本化",
    },
    {
        "theme": "AI泡沫论",
        "alias": "AI Bubble",
        "triggers": ["us_sp500 > 6500", "us_vixy > 20", "us_yield_curve < 0.95"],
        "strength_signals": ["us_sp500", "us_vixy"],
        "risk": "warning",
        "description": "AI估值过高+利率倒挂 → 类似2000年互联网泡沫",
        "peak_signal": "当出租车司机都在讨论AI股票 → 顶部信号",
        "contra_narrative": "AI是第四次工业革命，不是泡沫，估值合理",
    },
    {
        "theme": "美帝衰落论",
        "alias": "US Decline",
        "triggers": ["usd_reserve_share < 60", "us_political_polarization > 75", "us_debt_gdp > 120"],
        "strength_signals": ["usd_reserve_share", "us_political_polarization", "us_wealth_gap"],
        "risk": "warning",
        "description": "政治极化+财政失控+储备下降 → 美国霸权黄昏",
        "peak_signal": "当The Economist封面是'美国衰落' → 过度共识",
        "contra_narrative": "美国制度韧性+科技创新仍无可替代",
    },
    {
        "theme": "战争恐慌",
        "alias": "War Panic",
        "triggers": ["us_vixy > 25", "gold > 4500", "us_uso > 140"],
        "strength_signals": ["us_vixy", "gold", "us_uso"],
        "risk": "danger",
        "description": "多战区风险+避险资产齐涨 → 战争预期升温",
        "peak_signal": "当社交媒体被战争话题淹没 → 短期顶部",
        "contra_narrative": "核威慑有效，大国直接冲突概率极低",
    },
    {
        "theme": "美联储转向",
        "alias": "Fed Pivot",
        "triggers": ["us_unemployment > 4.5", "us_yield_curve < 0.90"],
        "strength_signals": ["us_unemployment", "us_yield_curve", "us_cpi"],
        "risk": "positive",
        "description": "经济走弱+利率倒挂 → Fed 被迫转向降息",
        "peak_signal": "当市场100%定价降息 → 预期已充分",
        "contra_narrative": "通胀未死，Fed不敢轻易转向",
    },
]


# ═══════════════════════════════════════════════════════
#  分析引擎
# ═══════════════════════════════════════════════════════

def _check_narrative_trigger(triggers: list[str], indicators: dict) -> bool:
    """检查叙事触发条件。OR 关系 — 任一满足即可。"""
    met_count = 0
    for cond in triggers:
        parts = cond.split()
        if len(parts) != 3:
            continue
        name, op, threshold_str = parts
        val = indicators.get(name)
        if val is None:
            continue
        threshold = float(threshold_str)
        if op == ">" and val > threshold:
            met_count += 1
        elif op == "<" and val < threshold:
            met_count += 1
    return met_count >= 2  # 至少满足 2 个触发条件


def _compute_strength(signals: list[str], indicators: dict) -> float:
    """计算叙事强度 0-1，基于信号指标偏离正常值程度。"""
    score = 0.0
    count = 0
    for sig in signals:
        val = indicators.get(sig)
        if val is None:
            continue
        count += 1
        # 简化的强度计算 — 用 Z-score 近似
        if sig == "gold":
            score += min(1.0, (val - 2000) / 3000)  # gold > 5000 = 1.0
        elif sig == "us_cpi":
            score += min(1.0, val / 6)  # cpi 6% = 1.0
        elif sig == "us_unemployment":
            score += min(1.0, val / 8)
        elif sig == "us_vixy":
            score += min(1.0, val / 40)
        elif sig == "em_eem":
            score += min(1.0, val / 100)
        elif sig == "us_sp500":
            score += min(1.0, val / 8000)
        elif sig == "us_yield_curve":
            score += max(0.0, (1.0 - val) / 0.3)  # curve < 0.7 = 1.0
        elif sig == "china_debt_gdp":
            score += min(1.0, val / 350)
        elif sig == "china_pmi":
            score += max(0.0, (50 - val) / 10)  # pmi < 40 = 1.0
        elif sig == "china_cpi":
            score += max(0.0, (2 - val) / 3) if val < 2 else min(1.0, (val - 2) / 6)
        elif sig == "usd_reserve_share":
            score += max(0.0, (70 - val) / 30)
        elif sig == "us_political_polarization":
            score += min(1.0, val / 100)
        elif sig == "us_wealth_gap":
            score += min(1.0, val / 0.5)
        elif sig == "us_uso":
            score += min(1.0, val / 200)
    return score / max(1, count)


def analyze() -> list[dict]:
    """分析当前活跃的主流叙事。

    Returns:
        [{theme, alias, strength, risk, met_triggers, total_triggers,
          description, peak_signal, contra_narrative}, ...]
    """
    snap = get_snapshot()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    results = []
    for n in NARRATIVES:
        triggered = _check_narrative_trigger(n["triggers"], indicators)
        if not triggered:
            continue

        strength = _compute_strength(n["strength_signals"], indicators)

        # 动态风险判断
        risk = n["risk"]
        if strength > 0.8:
            risk = "danger"  # 极端共识 = 反转风险
        elif strength > 0.6:
            risk = "warning"

        results.append({
            "theme": n["theme"],
            "alias": n["alias"],
            "strength": round(strength, 2),
            "risk": risk,
            "description": n["description"],
            "peak_signal": n["peak_signal"],
            "contra_narrative": n["contra_narrative"],
        })

    results.sort(key=lambda x: x["strength"], reverse=True)
    return results


def detect_narrative_shift(history: list = None) -> list[dict]:
    """检测叙事转折点。

    转折信号：
    - 新叙事强度快速上升（>0.5 且过去未出现）
    - 旧叙事强度骤降（>0.3 的跌幅）
    - 叙事与数据背离（高共识 vs 弱数据）
    """
    # TODO: 需要历史叙事记录，当前为占位框架
    return []


def format_report(narratives: list[dict]) -> str:
    """格式化叙事分析报告。"""
    if not narratives:
        return "当前暂无活跃的主流叙事。"

    lines = [
        "═" * 55,
        "  Dalio 叙事分析",
        "  主流市场叙事追踪",
        "═" * 55,
    ]

    for n in narratives:
        risk_icon = {"positive": "🟢", "warning": "🟡", "danger": "🔴"}.get(n["risk"], "⚪")
        bar_len = int(n["strength"] * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"\n  {risk_icon} {n['theme']} [{n['alias']}]")
        lines.append(f"     强度: {n['strength']:.0%} {bar}")
        lines.append(f"     描述: {n['description']}")
        lines.append(f"     ⚠ 反转信号: {n['peak_signal']}")
        lines.append(f"     💡 反叙事: {n['contra_narrative']}")

    # 共识风险警告
    high_strength = [n for n in narratives if n["strength"] > 0.7]
    if high_strength:
        names = "、".join(n["theme"] for n in high_strength)
        lines.append(f"\n  ⚠️ 过度共识警报: {names}")
        lines.append(f"     Dalio: 当所有人都相信一个叙事时，就是反转前夜")

    return "\n".join(lines)


if __name__ == "__main__":
    result = analyze()
    print(format_report(result))
