"""系统动力引擎 V2 — 稳定器失效检测 + 回路相互作用 + 系统相变预警。

V2 新增（P1）：
1. 稳定器失效检测 — 量化健康度 → 检测"失效进行中"
2. 回路相互作用矩阵 — 8×8 交叉影响分析
3. 系统相变预警 — 放大器/稳定器比例越过临界点

Dalio 最警惕的时刻：
"当负反馈（稳定器）失效，只剩正反馈（放大器）在运行 → 系统性崩溃前兆"
"""

import sys
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, DB_PATH

# 复用 V1 的回路定义
from engine.system_dynamics import LOOPS


# ═══════════════════════════════════════════════════════
#  稳定器健康度量化
# ═══════════════════════════════════════════════════════

def quantify_stabilizer_health(loop_id: str, loop: dict, indicators: dict) -> dict:
    """量化单个稳定器的健康度（而非定性标签）。
    
    健康度分数 (0-100):
    - 100 = 完美运行，空间充足
    - 60-80 = 可用但有限制
    - 30-60 = 脆弱，可能失效
    - 0-30 = 基本失效
    
    Returns:
        {health_score, health_level, failure_signals, space_remaining}
    """
    health = loop.get("health", "normal")
    failures = []
    score = 50  # 默认
    
    if loop_id == "fed_put":
        # Fed 看跌期权 — 取决于降息空间
        fed_rate = indicators.get("us_fed_rate", 4)
        cpi = indicators.get("us_cpi", 3)
        unemployment = indicators.get("us_unemployment", 5)
        
        # 降息空间 = 实际利率 - 中性利率(2%) 的余量
        real_rate = fed_rate - (cpi if cpi > 0 else 2)
        space = fed_rate  # 名义降息空间
        
        if space > 4:
            score = 90  # 充足
        elif space > 2:
            score = 70  # 足够
        elif space > 1:
            score = 45  # 有限
            failures.append(f"Fed 降息空间仅{space:.1f}%")
        else:
            score = 20  # 几乎用完
            failures.append(f"Fed 降息空间耗尽({space:.1f}%)")
        
        if cpi > 4:
            score = max(score - 20, 5)
            failures.append(f"通胀{cpi:.1f}%限制Fed行动")
        if unemployment < 3.5:
            score = max(score - 10, 5)
            failures.append("就业过热限制降息")
        
        level = "healthy" if score > 65 else ("available" if score > 35 else "fragile")
    
    elif loop_id == "supply_demand_rebalance":
        # 供需调节 — 价格机制是否仍然有效
        vix = indicators.get("us_vixy", 20)
        gold_yr = _gold_yoy(indicators)
        
        score = 75  # 基础良好
        if vix > 30:
            score -= 20
            failures.append(f"VIX={vix}恐慌破坏价格发现")
        if gold_yr > 50:
            score -= 15
            failures.append(f"黄金年涨{gold_yr:.0f}%→投机压倒供需")
        if abs(gold_yr) > 100:
            score = 20
            failures.append("价格机制基本失效")
        
        level = "healthy" if score > 65 else ("available" if score > 35 else "fragile")
    
    elif loop_id == "china_policy_response":
        # 中国政策 — 财政/货币空间
        debt = indicators.get("china_debt_gdp", 280)
        pmi = indicators.get("china_pmi", 50)
        cpi = indicators.get("china_cpi", 1)
        
        # 财政空间
        if debt < 250:
            fiscal_score = 90
        elif debt < 300:
            fiscal_score = 60
        elif debt < 350:
            fiscal_score = 35
            failures.append(f"地方债务{debt}%限制财政扩张")
        else:
            fiscal_score = 15
            failures.append(f"债务{debt}%→财政空间耗尽")
        
        # 货币空间（通缩比通胀更灵活）
        if cpi < 0:
            monetary_score = 80  # 通缩时降息空间大
        elif cpi < 2:
            monetary_score = 70
        elif cpi < 4:
            monetary_score = 45
        else:
            monetary_score = 20
            failures.append(f"CPI={cpi}%限制货币宽松")
        
        # 政策工具可用性
        if pmi < 48:
            failures.append(f"PMI={pmi}→需要政策但空间缩小")
        
        score = (fiscal_score * 0.5 + monetary_score * 0.5)
        level = "healthy" if score > 65 else ("available" if score > 35 else "fragile")
    
    elif loop_id == "global_cooperation":
        # 全球合作 — 最依赖政治意愿
        polarization = indicators.get("us_political_polarization", 70)
        reserve = indicators.get("usd_reserve_share", 58)
        gold = indicators.get("gold", 4000)
        vix = indicators.get("us_vixy", 20)
        
        score = 50  # 基础分
        if polarization > 80:
            score -= 20
            failures.append(f"极化{polarization}→国际合作瘫痪")
        if reserve < 55:
            score -= 15
            failures.append(f"储备份额{reserve}%→美国领导力下降")
        if gold > 5000:
            score -= 10
            failures.append(f"金价{int(gold)}→信任危机")
        if vix > 30:
            score -= 10
            failures.append(f"VIX={vix}→危机模式削弱合作")
        
        score = max(score, 5)
        level = "healthy" if score > 65 else ("available" if score > 35 else "fragile")
    
    else:
        score = 50
        level = "normal"
    
    return {
        "health_score": round(score, 1),
        "health_level": level,
        "failure_signals": failures,
        "is_degrading": score < 35,
    }


def _gold_yoy(indicators: dict) -> float:
    """计算黄金年涨幅。"""
    gold_now = indicators.get("gold", 0)
    gold_ref = indicators.get("gold_1y_reference", 0)
    if gold_ref and gold_ref > 0:
        return (gold_now - gold_ref) / gold_ref * 100
    return 0


# ═══════════════════════════════════════════════════════
#  回路相互作用矩阵
# ═══════════════════════════════════════════════════════

INTERACTIONS = {
    # (回路A, 回路B): {effect, strength, description}
    # effect: "amplify"(A加强B), "dampen"(A削弱B), "compete"(争夺同一资源), "trigger"(A触发B)
    
    ("wealth_effect_spiral", "fed_put"): {
        "effect": "dampen",
        "strength": 0.6,
        "description": "财富效应越强 → Fed 越倾向加息 → 削弱看跌期权",
    },
    ("wealth_effect_spiral", "gold_fomo_spiral"): {
        "effect": "compete",
        "strength": 0.5,
        "description": "股票 vs 黄金争夺资金 → 一个强则另一个弱",
    },
    ("debt_deflation_spiral", "china_policy_response"): {
        "effect": "trigger",
        "strength": 0.8,
        "description": "债务通缩升级 → 触发中国强力政策响应",
    },
    ("debt_deflation_spiral", "supply_demand_rebalance"): {
        "effect": "dampen",
        "strength": 0.7,
        "description": "通缩破坏价格信号 → 供需调节失效",
    },
    ("dollar_confidence_spiral", "gold_fomo_spiral"): {
        "effect": "amplify",
        "strength": 0.9,
        "description": "美元信心↓ ↔ 黄金FOMO↑ 是同一枚硬币的两面",
    },
    ("dollar_confidence_spiral", "fed_put"): {
        "effect": "dampen",
        "strength": 0.7,
        "description": "美元信心危机 → Fed 无法降息(通胀风险) → 看跌期权失效",
    },
    ("dollar_confidence_spiral", "global_cooperation"): {
        "effect": "dampen",
        "strength": 0.6,
        "description": "去美元化 → 美国领导力↓ → 全球合作减弱",
    },
    ("gold_fomo_spiral", "supply_demand_rebalance"): {
        "effect": "dampen",
        "strength": 0.5,
        "description": "投机狂热压倒供需基本面 → 价格发现扭曲",
    },
    ("populist_feedback", "global_cooperation"): {
        "effect": "dampen",
        "strength": 0.8,
        "description": "民粹政治 → 民族主义 → 国际合作崩溃",
    },
    ("populist_feedback", "fed_put"): {
        "effect": "dampen",
        "strength": 0.5,
        "description": "民粹施压 → Fed 独立性受威胁 → 政策可信度下降",
    },
    ("geopolitical_escalation_spiral", "supply_demand_rebalance"): {
        "effect": "dampen",
        "strength": 0.7,
        "description": "冲突切断供应链 → 价格信号扭曲(管制/制裁)",
    },
    ("geopolitical_escalation_spiral", "china_policy_response"): {
        "effect": "trigger",
        "strength": 0.6,
        "description": "外部围堵 → 中国加速自主可控/内循环",
    },
}


def analyze_interactions(active_loops: list[str]) -> list[dict]:
    """分析活跃回路之间的相互作用。"""
    results = []
    
    for (a, b), interaction in INTERACTIONS.items():
        both_active = a in active_loops and b in active_loops
        one_active = a in active_loops or b in active_loops
        
        if both_active:
            severity = "active"
        elif one_active:
            severity = "latent"
        else:
            severity = "dormant"
        
        results.append({
            "loop_a": a,
            "loop_b": b,
            "effect": interaction["effect"],
            "strength": interaction["strength"],
            "description": interaction["description"],
            "severity": severity,
        })
    
    # 按 severity + strength 排序
    results.sort(key=lambda x: (0 if x["severity"] == "active" else 1 if x["severity"] == "latent" else 2, -x["strength"]))
    return results


# ═══════════════════════════════════════════════════════
#  系统相变预警
# ═══════════════════════════════════════════════════════

def detect_phase_transition(amplifier_count: int, stabilizer_scores: list[float],
                            active_interactions: list[dict]) -> dict:
    """检测系统是否接近相变临界点。
    
    类比 Ising 模型：当"有序"力量（稳定器）减弱，"无序"力量（放大器）增强，
    系统会越过临界点发生相变——从"正常波动"切换到"危机模式"。
    
    临界指标：
    1. A/S比: 放大器数 / 健康稳定器数
    2. 净健康度: Σ稳定器健康分 - Σ放大器强度
    3. 相互作用熵: 活跃互作用的混乱程度
    """
    # 健康稳定器 = score > 50
    healthy_stabilizers = sum(1 for s in stabilizer_scores if s > 50)
    fragile_stabilizers = sum(1 for s in stabilizer_scores if s <= 35)
    
    # A/S 比
    if healthy_stabilizers > 0:
        as_ratio = amplifier_count / healthy_stabilizers
    else:
        as_ratio = amplifier_count / 0.5  # 避免除零，极大值
    
    # 净健康度
    net_health = sum(stabilizer_scores) - amplifier_count * 20
    
    # 活跃破坏性互作用数（effect=dampen 且 severity=active）
    destructive = [i for i in active_interactions 
                   if i["severity"] == "active" and i["effect"] == "dampen"]
    
    # 相变判断
    phase = "stable"
    warnings = []
    
    if as_ratio > 2.0:
        phase = "critical"
        warnings.append(f"⚠️ A/S比={as_ratio:.1f} — 放大器数量远超健康稳定器")
    elif as_ratio > 1.2:
        phase = "warning"
        warnings.append(f"🟡 A/S比={as_ratio:.1f} — 系统承压")
    elif as_ratio > 0.8:
        phase = "elevated"
    else:
        phase = "stable"
    
    if net_health < -30:
        phase = "critical"
        warnings.append(f"🚨 净健康度={net_health:.0f} — 稳定器总力量不足以对抗放大器")
    elif net_health < 0:
        if phase == "stable":
            phase = "elevated"
        warnings.append(f"🟡 净健康度={net_health:.0f} — 稳定器正在被消耗")
    
    if fragile_stabilizers >= 2:
        warnings.append(f"🔴 {fragile_stabilizers}个稳定器处于脆弱状态 — Dalio最危险的信号")
        if phase != "critical":
            phase = "warning"
    
    if len(destructive) >= 2:
        warnings.append(f"⚠️ {len(destructive)}个破坏性互作用同时活跃")
    
    # 最坏情况：系统性崩溃概率
    collapse_prob = 0.0
    if phase == "critical":
        collapse_prob = min(0.6, as_ratio * 0.15 + fragile_stabilizers * 0.15)
    elif phase == "warning":
        collapse_prob = min(0.3, as_ratio * 0.08 + fragile_stabilizers * 0.08)
    
    return {
        "phase": phase,
        "warnings": warnings,
        "as_ratio": round(as_ratio, 2),
        "net_health": round(net_health, 1),
        "healthy_stabilizers": healthy_stabilizers,
        "fragile_stabilizers": fragile_stabilizers,
        "destructive_interactions": len(destructive),
        "systemic_collapse_probability": round(collapse_prob, 3),
    }


# ═══════════════════════════════════════════════════════
#  主分析函数
# ═══════════════════════════════════════════════════════

def analyze_v2() -> dict:
    """V2 系统动力分析 — 完整版。"""
    snap = get_snapshot()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val
    
    # 1. 检查每个回路的活跃状态
    active_positive = []
    active_negative = []
    all_loop_ids = []
    
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
        
        if met:
            if loop["type"] == "positive":
                active_positive.append(lid)
            else:
                active_negative.append(lid)
        all_loop_ids.append(lid)
    
    # 2. 量化稳定器健康度
    stabilizer_details = {}
    stabilizer_scores = []
    for lid, loop in LOOPS.items():
        if loop["type"] == "negative":
            health = quantify_stabilizer_health(lid, loop, indicators)
            stabilizer_details[lid] = {
                "label": loop["label"],
                **health,
                "active": lid in active_negative,
            }
            stabilizer_scores.append(health["health_score"])
    
    # 3. 回路相互作用
    all_active = active_positive + active_negative
    interactions = analyze_interactions(all_active)
    active_interactions = [i for i in interactions if i["severity"] == "active"]
    
    # 4. 相变预警
    phase = detect_phase_transition(len(active_positive), stabilizer_scores, interactions)
    
    # 5. 综合
    n_pos = len(active_positive)
    n_healthy = sum(1 for s in stabilizer_scores if s > 50)
    n_fragile = sum(1 for s in stabilizer_scores if s <= 35)
    
    if phase["phase"] == "critical":
        criticality = "🔴 危险 — 系统接近相变临界点"
    elif phase["phase"] == "warning":
        criticality = "🟡 警惕 — 稳定器承压，放大器活跃"
    elif n_pos >= 3:
        criticality = "🟡 关注 — 多个放大器运行"
    else:
        criticality = "🟢 正常"
    
    return {
        "criticality": criticality,
        "n_pos": n_pos,
        "n_neg": len(active_negative),
        "n_healthy_stabilizers": n_healthy,
        "n_fragile_stabilizers": n_fragile,
        "active_positive_ids": active_positive,
        "active_negative_ids": active_negative,
        "stabilizer_details": stabilizer_details,
        "active_interactions": active_interactions,
        "all_interactions": interactions,
        "phase_transition": phase,
    }


# ═══════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    result = analyze_v2()
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"\n🔄 系统动力分析 V2")
        print(f"  系统状态: {result['criticality']}")
        print(f"  放大器: {result['n_pos']} | 稳定器: {result['n_neg']}")
        print(f"  健康: {result['n_healthy_stabilizers']} | 脆弱: {result['n_fragile_stabilizers']}")
        
        pt = result["phase_transition"]
        print(f"\n  📐 相变预警:")
        print(f"     A/S比: {pt['as_ratio']} | 净健康度: {pt['net_health']}")
        print(f"     相态: {pt['phase']} | 系统性崩溃概率: {pt['systemic_collapse_probability']:.1%}")
        for w in pt["warnings"]:
            print(f"     {w}")
        
        print(f"\n  🛡️ 稳定器健康度:")
        for lid, s in result["stabilizer_details"].items():
            bar = "█" * int(s["health_score"] / 5) + "░" * (20 - int(s["health_score"] / 5))
            icon = "🟢" if s["health_score"] > 65 else ("🟡" if s["health_score"] > 35 else "🔴")
            print(f"     {icon} {s['label']:12s} {s['health_score']:5.1f} {bar}")
            if s["failure_signals"]:
                for f in s["failure_signals"]:
                    print(f"        ↳ {f}")
        
        if result["active_interactions"]:
            print(f"\n  ⚡ 活跃的回路相互作用:")
            for i in result["active_interactions"][:5]:
                icon = {"amplify": "🔺", "dampen": "🔻", "compete": "⚔️", "trigger": "🔔"}.get(i["effect"], "→")
                print(f"     {icon} [{i['strength']:.1f}] {i['description']}")
