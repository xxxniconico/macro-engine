"""反向压力测试引擎 — Dalio 的"如果最坏情况发生"分析。

核心理念：从极端场景出发，回溯需要满足什么前置条件，
然后实时监控这些条件的激活度。

场景 → 前置条件 → 激活度监控 → 概率更新
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot


# ═══════════════════════════════════════════════════════
#  极端场景定义
# ═══════════════════════════════════════════════════════

SCENARIOS = {
    "us_debt_crisis": {
        "label": "美国债务危机",
        "severity": "extreme",
        "preconditions": [
            ("us_debt_gdp", ">", 130),
            ("usd_reserve_share", "<", 55),
            ("us_political_polarization", ">", 80),
            ("us_yield_curve", "<", 0.92),
        ],
        "assumed_impact": {
            "usd": "-30%（美元贬值）",
            "gold": "+50%（金价飙升）",
            "stocks": "-40%（美股暴跌）",
            "bonds": "US10Y +200bp（长端利率飙升）",
        },
        "description": "市场对美国国债信心崩溃 → 拍卖失败 → 美元储备地位急剧下降",
    },
    "china_hard_landing": {
        "label": "中国硬着陆",
        "severity": "severe",
        "preconditions": [
            ("china_debt_gdp", ">", 310),
            ("china_pmi", "<", 48),
            ("china_unemployment", ">", 6),
            ("china_cpi", "<", -0.5),
        ],
        "assumed_impact": {
            "CNY": "-15%（人民币贬值）",
            "commodities": "-30%（大宗暴跌）",
            "hong_kong": "-40%（港股重挫）",
            "global_gdp": "-1.5pp（拖累全球）",
        },
        "description": "房地产+地方政府债务螺旋 → 通缩 → 银行危机 → 经济硬着陆",
    },
    "global_stagflation": {
        "label": "全球滞胀",
        "severity": "severe",
        "preconditions": [
            ("us_cpi", ">", 4),
            ("china_cpi", ">", 3),
            ("us_unemployment", ">", 5),
            ("gold", ">", 5000),
        ],
        "assumed_impact": {
            "stocks": "-25%（全球股市）",
            "bonds": "滞胀 = 股债双杀",
            "commodities": "黄金$6000+，石油$150+",
        },
        "description": "供给冲击+货币宽松后遗症 → 通胀顽固+增长停滞 → 央行两难",
    },
    "reserve_currency_shift": {
        "label": "储备货币更替",
        "severity": "extreme",
        "preconditions": [
            ("usd_reserve_share", "<", 50),
            ("us_political_polarization", ">", 85),
            ("us_debt_gdp", ">", 140),
            ("gold", ">", 5500),
        ],
        "assumed_impact": {
            "order": "全球秩序重组",
            "usd": "-40-60%",
            "gold": "新的全球货币锚",
            "timeline": "5-15年过渡期",
        },
        "description": "美元储备份额跌破50% → 多极货币体系 → 类似1920s英镑到美元的过渡",
    },
    "japanification": {
        "label": "日本化（长期通缩停滞）",
        "severity": "moderate",
        "preconditions": [
            ("china_debt_gdp", ">", 300),
            ("china_cpi", "<", 0),
            ("china_population_growth", "<", -0.5),
            ("china_pmi", "<", 49),
        ],
        "assumed_impact": {
            "growth": "0-2% 长期低增长",
            "rates": "零利率常态化",
            "equity": "低回报+高波动",
        },
        "description": "人口下降+债务高企+通缩 → 日本式失去的三十年",
    },
    "ai_disruption_crisis": {
        "label": "AI 颠覆性失业危机",
        "severity": "moderate",
        "preconditions": [
            ("us_unemployment", ">", 6),
            ("technology_adoption_rate", ">", 80),  # 主观指标
            ("income_inequality_gini", ">", 0.45),
        ],
        "assumed_impact": {
            "jobs": "白领大规模失业",
            "society": "UBI 讨论加速",
            "markets": "科技股先涨后跌",
        },
        "description": "AI 替代白领工作 → 结构性失业 → 社会契约重写",
    },
}


# ═══════════════════════════════════════════════════════

def _get_indicator(snap: dict, name: str) -> Optional[float]:
    """从快照获取指标，支持别名。"""
    aliases = {
        "us_debt_gdp": ["us_debt_gdp", "us_govt_debt_gdp"],
        "us_political_polarization": ["us_political_polarization"],
        "us_yield_curve": ["us_yield_curve"],
        "usd_reserve_share": ["usd_reserve_share"],
        "china_debt_gdp": ["china_debt_gdp"],
        "china_pmi": ["china_pmi"],
        "china_cpi": ["china_cpi"],
        "china_unemployment": ["china_unemployment"],
        "china_population_growth": ["china_population_growth"],
        "income_inequality_gini": ["us_wealth_gap"],
        "us_unemployment": ["us_unemployment"],
        "us_cpi": ["us_cpi"],
        "gold": ["gold"],
        "technology_adoption_rate": [],  # 暂无数据
    }

    for alias in aliases.get(name, [name]):
        entry = snap.get(alias, {})
        val = entry.get("value")
        if val is not None:
            return val
    return None


def _check_precondition(snap: dict, indicator: str, op: str, threshold: float) -> bool:
    val = _get_indicator(snap, indicator)
    if val is None:
        return None  # 数据不可用
    if op == ">":
        return val > threshold
    if op == "<":
        return val < threshold
    if op == ">=":
        return val >= threshold
    if op == "<=":
        return val <= threshold
    return False


def monitor() -> dict:
    """监控所有极端场景的前置条件激活度。

    Returns:
        {scenario_id: {label, severity, activation_pct, met_count, total_count,
                       status, assumed_impact, description, details: [...]}}
    """
    snap = get_snapshot()
    results = {}

    for scenario_id, scenario in SCENARIOS.items():
        met = 0
        total = len(scenario["preconditions"])
        unavailable = 0
        details = []

        for indicator, op, threshold in scenario["preconditions"]:
            val = _get_indicator(snap, indicator)
            if val is None:
                unavailable += 1
                details.append({"indicator": indicator, "condition": f"{indicator} {op} {threshold}",
                                "current": "N/A", "met": False, "available": False})
                continue

            condition_met = _check_precondition(snap, indicator, op, threshold)
            details.append({
                "indicator": indicator,
                "condition": f"{indicator} {op} {threshold}",
                "current": val,
                "met": condition_met,
                "available": True,
            })
            if condition_met:
                met += 1

        effective_total = total - unavailable
        if effective_total > 0:
            activation_pct = met / effective_total * 100
        else:
            activation_pct = 0

        if activation_pct >= 70:
            status = "🔴 高危"
            color = "red"
        elif activation_pct >= 40:
            status = "🟡 关注"
            color = "yellow"
        else:
            status = "🟢 低概率"
            color = "green"

        results[scenario_id] = {
            "label": scenario["label"],
            "severity": scenario["severity"],
            "activation_pct": round(activation_pct, 1),
            "met_count": met,
            "total_count": effective_total,
            "unavailable_count": unavailable,
            "status": status,
            "color": color,
            "description": scenario["description"],
            "assumed_impact": scenario["assumed_impact"],
            "details": details,
        }

    return results


def format_report(monitor_result: dict) -> str:
    """格式化压力测试监控报告。"""
    lines = [
        "═" * 55,
        "  Dalio 反向压力测试",
        "  极端场景前置条件监控",
        "═" * 55,
    ]

    sorted_scenarios = sorted(monitor_result.values(),
                              key=lambda x: x["activation_pct"], reverse=True)

    for s in sorted_scenarios:
        severity_icon = {"extreme": "💀", "severe": "🔴", "moderate": "🟡"}.get(s["severity"], "⚪")
        lines.append(f"\n  {severity_icon} {s['status']} {s['label']} [{s['severity']}]")
        unavail_info = f", {s['unavailable_count']}项数据缺失" if s['unavailable_count'] else ""
        lines.append(f"     激活度: {s['activation_pct']}% ({s['met_count']}/{s['total_count']} 条件满足{unavail_info})")
        lines.append(f"     描述: {s['description']}")

        # 详细条件
        for d in s["details"]:
            if d["available"]:
                icon = "✓" if d["met"] else "✗"
                lines.append(f"       {icon} {d['condition']} → 当前: {d['current']}")
            else:
                lines.append(f"       ? {d['condition']} → 数据缺失")

    return "\n".join(lines)


if __name__ == "__main__":
    result = monitor()
    print(format_report(result))
    print()

    # 主关注场景
    print("═══ 需要关注的场景 ═══")
    for sid, s in result.items():
        if s["activation_pct"] >= 40:
            print(f"  {s['status']} {s['label']}: {s['activation_pct']}% 激活")
