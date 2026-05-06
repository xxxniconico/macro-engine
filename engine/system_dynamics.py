"""系统动力引擎 — Dalio 框架的系统动力视角。

核心理念：经济系统 = 多个正/负反馈回路叠加。
最危险的时刻：当负反馈（稳定器）失效，只剩正反馈（放大器）在运行。

监测维度：
1. 活跃的正反馈回路（可能失控）
2. 负反馈回路是否有效
3. 系统临界状态
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot


# ═══════════════════════════════════════════════════════
#  反馈回路定义
#  正反馈 = 放大器（可能失控）  负反馈 = 稳定器（系统自我修正）
# ═══════════════════════════════════════════════════════

LOOPS = {
    # ── 正反馈（放大器）──
    "wealth_effect_spiral": {
        "label": "财富效应正螺旋",
        "type": "positive",
        "description": "股价涨 → 财富效应 → 消费↑ → 企业利润↑ → 股价再涨",
        "conditions": ["us_sp500 > 6000", "us_unemployment < 5"],
        "risk": "泡沫形成 → 杠杆累积 → 最终破裂",
        "status": "inactive",
    },
    "debt_deflation_spiral": {
        "label": "债务通缩螺旋",
        "type": "positive",
        "description": "通缩 → 实际债务负担↑ → 削减支出 → 更多通缩",
        "conditions": ["china_cpi < 0.5", "china_debt_gdp > 280"],
        "risk": "日本化 → 失去的三十年 → 社会停滞",
        "status": "inactive",
    },
    "dollar_confidence_spiral": {
        "label": "美元信心负螺旋",
        "type": "positive",
        "description": "去美元化 → 美债需求↓ → 利率↑ → 财政恶化 → 更多去美元化",
        "conditions": ["usd_reserve_share < 58", "gold > 4500"],
        "risk": "美元储备地位动摇 → 全球秩序重组",
        "status": "inactive",
    },
    "gold_fomo_spiral": {
        "label": "黄金 FOMO 螺旋",
        "type": "positive",
        "description": "金价涨 → 央行/散户追买 → 金价再涨 → 验证\"避险\"叙事",
        "conditions": ["gold > 4000"],
        "risk": "投机性泡沫 → 剧烈回调 → 反噬去美元化叙事",
        "status": "inactive",
    },
    "populist_feedback": {
        "label": "民粹自我强化",
        "type": "positive",
        "description": "贫富差距 → 民粹上台 → 极端政策 → 社会撕裂 → 更多民粹",
        "conditions": ["us_political_polarization > 75", "us_wealth_gap > 0.40"],
        "risk": "政治极化不可逆 → 制度失效 → 宪政危机",
        "status": "inactive",
    },
    "geopolitical_escalation_spiral": {
        "label": "地缘升级螺旋",
        "type": "positive",
        "description": "冲突 → 制裁 → 反制裁 → 脱钩 → 更多冲突",
        "conditions": ["us_vixy > 20", "gold > 4500", "us_uso > 130"],
        "risk": "全面对抗 → 两大阵营 → 冷战2.0/热战",
        "status": "inactive",
    },

    # ── 负反馈（稳定器）──
    "fed_put": {
        "label": "Fed 看跌期权",
        "type": "negative",
        "description": "市场暴跌 → Fed紧急降息/QE → 市场企稳",
        "conditions": ["us_fed_rate > 3"],
        "health": "healthy",  # 目前利率空间充足
        "status": "inactive",
    },
    "supply_demand_rebalance": {
        "label": "供需自我调节",
        "type": "negative",
        "description": "价格过高 → 需求下降 → 价格回落 → 需求恢复",
        "conditions": [],
        "health": "normal",
        "status": "inactive",
    },
    "china_policy_response": {
        "label": "中国政策响应",
        "type": "negative",
        "description": "经济恶化 → 政策加码 → 经济企稳",
        "conditions": ["china_pmi > 48"],  # PMI > 48 仍有政策空间
        "health": "available",
        "status": "inactive",
    },
    "global_cooperation": {
        "label": "全球合作机制",
        "type": "negative",
        "description": "危机 → 国际合作(IMF/G20/BIS) → 协调应对",
        "conditions": [],
        "health": "fragile",  # 当前合作机制弱化
        "status": "inactive",
    },
}


# ═══════════════════════════════════════════════════════

def analyze() -> dict:
    """分析当前活跃的反馈回路和系统稳定性。"""
    snap = get_snapshot()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    active_positive = []
    active_negative = []
    stabilizers_status = []

    for lid, loop in LOOPS.items():
        conditions = loop["conditions"]
        met = True
        for cond in conditions:
            parts = cond.split()
            if len(parts) == 3:
                name, op, threshold_str = parts
                val = indicators.get(name)
                if val is None:
                    met = False
                    break
                threshold = float(threshold_str)
                if op == ">" and not (val > threshold):
                    met = False
                elif op == "<" and not (val < threshold):
                    met = False

        loop_entry = {
            "label": loop["label"],
            "description": loop["description"],
            "type": loop["type"],
            "risk": loop.get("risk", ""),
            "health": loop.get("health", ""),
            "active": met,
        }

        if met:
            if loop["type"] == "positive":
                active_positive.append(loop_entry)
            else:
                active_negative.append(loop_entry)

        if loop["type"] == "negative":
            stabilizers_status.append(loop_entry)

    # 系统临界状态评估
    n_pos_active = len(active_positive)
    n_neg_active = len(active_negative)
    n_neg_healthy = sum(1 for s in stabilizers_status
                        if s.get("health") in ("healthy", "available"))

    if n_pos_active >= 4 and n_neg_healthy < 2:
        criticality = "🔴 危险 — 多放大器运行 + 稳定器不足"
    elif n_pos_active >= 3:
        criticality = "🟡 警惕 — 多个正反馈活跃"
    elif n_pos_active >= 1:
        criticality = "🟢 正常 — 关注放大器"
    else:
        criticality = "🟢 正常"

    return {
        "active_positive": active_positive,
        "active_negative": active_negative,
        "all_stabilizers": stabilizers_status,
        "criticality": criticality,
        "n_pos": n_pos_active,
        "n_neg": n_neg_active,
        "n_healthy_stabilizers": n_neg_healthy,
    }


def format_report(result: dict) -> str:
    """格式化系统动力分析报告。"""
    lines = [
        "═" * 55,
        "  Dalio 系统动力分析",
        "  正负反馈回路监测",
        "═" * 55,
        "",
        f"  系统状态: {result['criticality']}",
        f"  活跃正反馈(放大器): {result['n_pos']}",
        f"  活跃负反馈(稳定器): {result['n_neg']}",
        f"  健康稳定器: {result['n_healthy_stabilizers']}",
    ]

    if result["active_positive"]:
        lines.append("\n  ═══ 🔺 活跃放大器（正反馈）═══")
        for loop in result["active_positive"]:
            lines.append(f"\n  ⚠ {loop['label']}")
            lines.append(f"     {loop['description']}")
            lines.append(f"     💀 风险: {loop['risk']}")

    if result["active_negative"]:
        lines.append("\n  ═══ 🔻 活跃稳定器（负反馈）═══")
        for loop in result["active_negative"]:
            lines.append(f"\n  ✓ {loop['label']}")
            lines.append(f"     {loop['description']}")

    # 稳定器健康报告
    lines.append("\n  ═══ 🛡️ 稳定器健康报告 ═══")
    for s in result["all_stabilizers"]:
        health = s.get("health", "unknown")
        icon = {"healthy": "🟢", "available": "🟡", "fragile": "🔴"}.get(health, "⚪")
        status = "活跃" if s["active"] else "休眠"
        lines.append(f"  {icon} {s['label']}: {health} ({status})")

    # Dalio 最警惕的时刻
    if result["n_pos"] >= 3 and result["n_healthy_stabilizers"] < 2:
        lines.append(f"\n  🚨 Dalio 最警惕的时刻：")
        lines.append(f"     当稳定器失效，只剩放大器运行时 = 系统性崩溃前兆")

    return "\n".join(lines)


if __name__ == "__main__":
    result = analyze()
    print(format_report(result))
