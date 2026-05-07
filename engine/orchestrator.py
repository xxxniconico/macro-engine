"""Dalio 协同总指挥 — 6步分析流程自动化 + 动态视角加权 + 仓位输出。

核心理念（深度研究 3.1/3.2/六）：
Dalio 框架 ≠ 8个独立视角的集合
Dalio 框架 = 8个视角按权重协同，形成「互相校验的立体决策系统」

流程：
  Step 1: 模板匹配 → 历史类比
  Step 2: 周期定位 → 知当前位置
  Step 3: 因果推演 → 链式传导
  Step 4: 博弈分析 → 各方应对
  Step 5: 压力测试 → 极端场景
  Step 6: 概率合成 → 加权输出 → 仓位建议

动态权重（深度研究 3.2）：
  正常增长期: 周期+因果主导
  泡沫形成期: 叙事+因果主导
  危机爆发期: 历史+压力测试主导
  去杠杆期:   博弈+第一性原理主导
  秩序更替期: 历史+系统动力主导
"""

import json
import sys
from pathlib import Path
from datetime import date
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# ═══════════════════════════════════════════════════════
#  动态视角权重表（深度研究 3.2）
# ═══════════════════════════════════════════════════════

PHASE_WEIGHTS = {
    "normal_growth": {
        "label": "正常增长期",
        "description": "经济温和扩张，无极端信号",
        "weights": {
            "cycle": 0.30,        # 周期定位
            "causal": 0.25,       # 因果链条
            "template": 0.15,     # 历史类比
            "system": 0.10,       # 系统动力
            "narrative": 0.08,    # 叙事
            "game": 0.05,         # 博弈
            "stress": 0.04,       # 压力测试
            "first_principles": 0.03,  # 第一性原理
        },
    },
    "bubble_forming": {
        "label": "泡沫形成期",
        "description": "资产价格脱离基本面，叙事自我强化",
        "weights": {
            "narrative": 0.30,    # 叙事追踪（最重要）
            "causal": 0.20,       # 因果链条
            "template": 0.18,     # 历史类比（上次泡沫怎么破的）
            "stress": 0.12,       # 压力测试
            "cycle": 0.08,
            "game": 0.05,
            "system": 0.04,
            "first_principles": 0.03,
        },
    },
    "crisis_unfolding": {
        "label": "危机爆发期",
        "description": "市场剧烈波动，系统性风险实现",
        "weights": {
            "template": 0.28,     # 历史类比（关键）
            "stress": 0.25,       # 压力测试（最坏情况）
            "game": 0.18,         # 博弈（各方怎么救）
            "causal": 0.12,       # 因果链条
            "first_principles": 0.07,
            "system": 0.05,
            "cycle": 0.03,
            "narrative": 0.02,    # 叙事在危机中不重要（恐慌主导）
        },
    },
    "deleveraging": {
        "label": "去杠杆期",
        "description": "债务削减，资产负债表修复，增长低迷",
        "weights": {
            "game": 0.28,         # 博弈（谁承担损失）
            "first_principles": 0.22,  # 第一性（债务本质）
            "cycle": 0.18,        # 周期定位
            "causal": 0.12,
            "system": 0.08,
            "stress": 0.06,
            "template": 0.04,
            "narrative": 0.02,
        },
    },
    "order_transition": {
        "label": "秩序更替期",
        "description": "全球秩序重组，储备货币动摇，帝国周期末期",
        "weights": {
            "template": 0.28,     # 历史类比（霸权更替模板）
            "system": 0.22,       # 系统动力（正负反馈）
            "narrative": 0.15,    # 叙事追踪
            "stress": 0.12,
            "game": 0.10,
            "first_principles": 0.07,
            "causal": 0.04,
            "cycle": 0.02,
        },
    },
}

DEFAULT_WEIGHTS = PHASE_WEIGHTS["normal_growth"]["weights"]


# ═══════════════════════════════════════════════════════
#  V2: 连续阶段打分 + 模糊权重融合
# ═══════════════════════════════════════════════════════

def score_phase_membership(cycle_result: dict, narrative: dict, system: dict,
                           stress_alerts: int = 0) -> dict:
    """对5个宏观阶段分别评分 (0-1)，而非二选一。

    每个阶段由多个信号驱动，得分=该阶段匹配程度。
    最终权重 = Σ(阶段得分 × 该阶段预设权重表)，平滑过渡。
    """
    empire = cycle_result.get("empire", {})
    long_term = cycle_result.get("long_term", {})
    short_term = cycle_result.get("short_term", {})
    bull_ratio = narrative.get("bull_ratio", 0.5) if isinstance(narrative, dict) else 0.5
    empire_stage = empire.get("stage", "")
    long_stage = long_term.get("stage", "")
    empire_score_abs = empire.get("score", 0)
    long_score_abs = long_term.get("score", 0)
    as_ratio = system.get("phase_transition", {}).get("as_ratio", 1.0) if isinstance(system, dict) else 1.0
    collapse_prob = system.get("phase_transition", {}).get("systemic_collapse_probability", 0) if isinstance(system, dict) else 0

    scores = {p: 0.0 for p in PHASE_WEIGHTS}

    # ── order_transition (帝国秩序更替) ──
    order_score = 0.0
    if "内部冲突" in empire_stage or "秩序" in empire_stage: order_score += 0.40
    if "泡沫" in empire_stage: order_score += 0.25
    if empire_score_abs < -0.15: order_score += 0.15
    # 储备份额持续下降是帝国衰落的强信号
    order_score = min(order_score, 0.95)
    scores["order_transition"] = order_score

    # ── deleveraging (去杠杆) ──
    delever_score = 0.0
    if "去杠杆" in long_stage: delever_score += 0.50
    if long_score_abs < -0.1: delever_score += 0.20
    # 如果长期周期得分低+帝国也在恶化 → 去杠杆概率更高
    if empire_score_abs < -0.1: delever_score += 0.10
    delever_score = min(delever_score, 0.95)
    scores["deleveraging"] = delever_score

    # ── crisis_unfolding (危机爆发) ──
    crisis_score = 0.0
    if stress_alerts >= 5: crisis_score += 0.50
    elif stress_alerts >= 3: crisis_score += 0.25
    if as_ratio > 1.5: crisis_score += 0.15
    if collapse_prob > 0.15: crisis_score += 0.15
    crisis_score = min(crisis_score, 0.95)
    scores["crisis_unfolding"] = crisis_score

    # ── bubble_forming (泡沫形成) ──
    bubble_score = 0.0
    if bull_ratio > 0.85: bubble_score += 0.40
    elif bull_ratio > 0.70: bubble_score += 0.20
    if bull_ratio < 0.15: bubble_score += 0.30  # 极端悲观也是泡沫的另一面
    # VIX 高位+叙事极端 = 经典泡沫信号
    if as_ratio > 1.2: bubble_score += 0.10
    bubble_score = min(bubble_score, 0.95)
    scores["bubble_forming"] = bubble_score

    # ── normal_growth (正常增长) ──
    # 正常=其他阶段都不强
    other_max = max(scores["order_transition"], scores["deleveraging"],
                    scores["crisis_unfolding"], scores["bubble_forming"])
    normal_score = max(0.0, 1.0 - other_max * 1.1)  # 其他阶段强时正常弱
    normal_score = min(normal_score, 0.95)
    scores["normal_growth"] = normal_score

    # 归一化确保总和=1
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    return scores


def compute_blended_weights(phase_scores: dict) -> dict:
    """模糊融合：Σ(阶段得分 × 该阶段权重表) → 平滑连续权重。"""
    blended = {}
    all_perspectives = list(DEFAULT_WEIGHTS.keys())

    for persp in all_perspectives:
        blended[persp] = sum(
            phase_scores.get(phase, 0) * PHASE_WEIGHTS[phase]["weights"].get(persp, 0)
            for phase in PHASE_WEIGHTS
        )

    # 归一化
    total = sum(blended.values())
    if total > 0:
        blended = {k: round(v / total, 4) for k, v in blended.items()}

    return blended


def detect_macro_phase_v2(cycle_result: dict, narrative: dict, system: dict,
                          stress_alerts: int = 0) -> tuple:
    """V2: 返回 (主阶段标签, 阶段得分, 融合权重, 所有阶段得分)。

    相比V1的离散决策树，V2输出连续权重，消除了权重跳变。
    """
    phase_scores = score_phase_membership(cycle_result, narrative, system, stress_alerts)
    blended_weights = compute_blended_weights(phase_scores)

    # 主阶段 = 得分最高的
    primary = max(phase_scores, key=phase_scores.get)
    primary_score = phase_scores[primary]
    primary_label = PHASE_WEIGHTS[primary]["label"]

    return primary, primary_label, primary_score, blended_weights, phase_scores

def detect_macro_phase(cycle_result: dict, narrative: dict, system: dict) -> str:
    """根据当前数据自动判断宏观阶段。
    
    决策树：
    1. 帝国周期处于内部冲突 + 储备份额<57% → order_transition
    2. 长期周期去杠杆 + 债务>300% → deleveraging
    3. 叙事极端(>0.8/<0.2) + VIX>25 → bubble_forming 或 crisis
    4. 压力测试多场景>25% → crisis_unfolding
    5. 默认 → normal_growth
    """
    # 帝国更替
    empire = cycle_result.get("empire", {})
    if "内部冲突" in empire.get("stage", "") or "秩序" in empire.get("stage", ""):
        return "order_transition"
    
    # 去杠杆
    long_term = cycle_result.get("long_term", {})
    if "去杠杆" in long_term.get("stage", ""):
        return "deleveraging"
    
    # 危机 / 泡沫
    from engine.stress_test_v2 import evaluate_all_scenarios
    try:
        st = evaluate_all_scenarios()
        n_alerts = sum(1 for s in st if s["probability"] > 0.25)
    except:
        n_alerts = 0
    
    if n_alerts >= 5:
        return "crisis_unfolding"
    
    bull_ratio = narrative.get("bull_ratio", 0.5) if isinstance(narrative, dict) else 0.5
    if bull_ratio > 0.75 or bull_ratio < 0.25:
        return "bubble_forming"
    
    return "normal_growth"


# ═══════════════════════════════════════════════════════
#  Step 1-6: 流水线
# ═══════════════════════════════════════════════════════

def step1_template_matching() -> dict:
    """Step 1: 历史模板匹配 + 差异分析。"""
    from engine.template_matcher import run_matcher
    from engine.historical_diff import analyze_template_diff
    
    match = run_matcher()
    if match.get("message"):
        return {"error": match["message"]}
    
    diff = analyze_template_diff(match)
    
    return {
        "top_matches": match["matches"][:5],
        "path_prediction": match.get("path_prediction", {}),
        "diff_analysis": diff,
        "summary": diff.get("summary", ""),
    }


def step2_cycle_positioning() -> dict:
    """Step 2: 三周期定位。"""
    from engine.cycle_locator import diagnose
    return diagnose()


def step3_causal_inference() -> dict:
    """Step 3: 因果推演 (V2 趋势感知)。"""
    from engine.causal_chain import detect_triggers_v2, traverse, CAUSAL_GRAPH

    triggers_v2 = detect_triggers_v2()
    active = [t for t in triggers_v2 if not t.get("is_approaching")]
    approaching = [t for t in triggers_v2 if t.get("is_approaching")]

    if not active:
        return {
            "active_triggers": [],
            "approaching_triggers": approaching,
            "future_events": [],
            "n_triggers": 0,
            "n_approaching": len(approaching),
            "summary": f"无触发 ({len(approaching)}逼近)" if approaching else "无触发",
        }

    seed_ids = [t["id"] for t in active]
    timeline = traverse(seed_ids)
    future = [e for e in timeline if e["expected_month"] > 0]

    return {
        "active_triggers": [
            {"id": t["id"], "label": t["label"], "strength": t["strength"], "detail": t.get("detail","")}
            for t in active
        ],
        "approaching_triggers": approaching,
        "future_events": future,
        "n_triggers": len(active),
        "n_approaching": len(approaching),
        "n_future": len(future),
        "summary": f"{len(active)}条因果链触发({len(approaching)}逼近)，{len(future)}个未来节点",
    }


def step4_game_theory() -> dict:
    """Step 4: 多方博弈。"""
    from engine.game_theory_v2 import analyze_v2 as game_v2
    return game_v2()


def step5_stress_test() -> dict:
    """Step 5: 反向压力测试。"""
    from engine.stress_test_v2 import evaluate_all_scenarios, get_active_alerts
    
    scenarios = evaluate_all_scenarios()
    alerts = get_active_alerts(scenarios, 0.20)
    
    return {
        "top_risks": scenarios[:8],
        "alerts": alerts,
        "n_scenarios": len(scenarios),
        "n_alerts": len(alerts),
        "extreme_count": sum(1 for s in scenarios if s["probability"] > 0.65),
        "high_count": sum(1 for s in scenarios if 0.40 < s["probability"] <= 0.65),
    }


def step6_synthesis(results: dict, phase_weights: dict) -> dict:
    """Step 6: 综合概率 → 场景 → 仓位。
    
    这是 Dalio 的「最后一公里」：
    各视角加权 → 场景概率分布 → 风险收益比 → 投资仓位
    """
    # ── 提取各视角的关键指标 ──
    cycle = results.get("cycle", {})
    stress = results.get("stress", {})
    narrative = results.get("narrative_full", {})
    system = results.get("system_dynamics", {})
    
    # ── 综合风险评分 (0-100) ──
    # 每个视角独立评估0-100，然后加权平均
    # 权重来自宏观阶段，但评分不应被权重过度稀释
    risk_score = 0.0
    total_weight = 0.0
    
    # 周期贡献 (30分基准)
    short_score = cycle.get("short_term", {}).get("score", 0)
    long_score = cycle.get("long_term", {}).get("score", 0)
    empire_score = cycle.get("empire", {}).get("score", 0)
    # 得分越低越危险：0→高风险，1→低风险
    cycle_risk = (0.3 - short_score) * 40 + (0.3 - long_score) * 30 + (0.3 - empire_score) * 30
    cycle_risk = max(0, min(100, cycle_risk))
    w = phase_weights.get("cycle", 0.15) * 5  # 放大权重差异
    risk_score += cycle_risk * w
    total_weight += w
    
    # 压力测试贡献 (50分基准)
    n_alerts = stress.get("n_alerts", 0)
    stress_risk = min(n_alerts * 8, 60) + stress.get("extreme_count", 0) * 20 + stress.get("high_count", 0) * 10
    w = phase_weights.get("stress", 0.10) * 5
    risk_score += stress_risk * w
    total_weight += w
    
    # 叙事贡献 (极端共识=风险)
    bull_ratio = 0.5
    if isinstance(narrative, dict):
        bull_ratio = narrative.get("bull_ratio", 0.5)
    narrative_risk = abs(bull_ratio - 0.5) * 2 * 100  # 分歧度0→0，完全一致1.0→100
    # 额外：极端共识+VIX背离
    if bull_ratio > 0.85:
        narrative_risk += 20  # 过度乐观=反转风险
    elif bull_ratio < 0.15:
        narrative_risk += 20  # 过度悲观=恐慌
    # VIX背离
    if isinstance(narrative, dict) and narrative.get("divergence", {}).get("divergence_score", 0) > 20:
        narrative_risk += 15
    w = phase_weights.get("narrative", 0.08) * 5
    risk_score += narrative_risk * w
    total_weight += w
    
    # 系统动力贡献
    collapse_prob = system.get("phase_transition", {}).get("systemic_collapse_probability", 0)
    as_ratio = system.get("phase_transition", {}).get("as_ratio", 0)
    system_risk = collapse_prob * 150 + max(0, (as_ratio - 0.8) * 30)
    system_risk = min(system_risk, 80)
    w = phase_weights.get("system", 0.08) * 5
    risk_score += system_risk * w
    total_weight += w
    
    # 模板差异贡献
    template = results.get("template", {})
    diff = template.get("diff_analysis", {})
    worse_count = diff.get("worse_count", 0)
    better_count = diff.get("better_count", 0)
    diff_ratio = worse_count / max(better_count, 1)
    template_risk = min(diff_ratio * 15, 60)
    w = phase_weights.get("template", 0.15) * 5
    risk_score += template_risk * w
    total_weight += w
    
    # 博弈贡献（市场高压）
    game = results.get("game_theory", {})
    players = game.get("players", [])
    n_high_pressure = sum(1 for p in players if "高压" in p.get("status", ""))
    game_risk = n_high_pressure * 15
    w = phase_weights.get("game", 0.05) * 5
    risk_score += game_risk * w
    total_weight += w
    
    # 因果链贡献
    causal = results.get("causal", {})
    n_triggers = causal.get("n_triggers", 0)
    causal_risk = min(n_triggers * 8, 40)
    w = phase_weights.get("causal", 0.12) * 5
    risk_score += causal_risk * w
    total_weight += w
    
    # 归一化
    if total_weight > 0:
        risk_score = risk_score / total_weight
    risk_score = min(risk_score, 95)
    risk_score = max(risk_score, 5)
    
    # ── 场景概率分布 ──
    scenarios_probs = {}
    for s in stress.get("top_risks", [])[:5]:
        scenarios_probs[s["label"]] = s["probability"]
    
    # 额外场景（从博弈+周期推断）
    game_tree = results.get("game_theory", {}).get("game_tree", {})
    for ts in game_tree.get("terminal_scenarios", []):
        if ts["name"] not in scenarios_probs:
            scenarios_probs[ts["name"]] = ts["probability"]
    
    # ── 风险收益比 ──
    # 简化：风险得分 → 预期收益修正
    if risk_score < 25:
        risk_reward = "🟢 有利 — 风险低，正常配置"
        base_equity = 0.60
    elif risk_score < 40:
        risk_reward = "🟡 中性 — 适度参与，注意对冲"
        base_equity = 0.50
    elif risk_score < 60:
        risk_reward = "🟠 谨慎 — 降低权益，增持对冲"
        base_equity = 0.35
    elif risk_score < 80:
        risk_reward = "🔴 防御 — 大幅降低风险敞口"
        base_equity = 0.20
    else:
        risk_reward = "💀 极端防御 — 现金为王"
        base_equity = 0.10
    
    # ── 投资仓位建议 ──
    # 基于 Dalio 全天候策略框架
    gold_weight = 0.07
    if isinstance(narrative, dict) and bull_ratio > 0.75:
        gold_weight = 0.15  # 极端看多时黄金对冲更重
    if collapse_prob > 0.15:
        gold_weight = 0.20  # 崩溃概率高时加黄金
    
    bond_weight = 1.0 - base_equity - gold_weight - 0.05  # 5%现金
    
    allocation = {
        "equity": {
            "weight": round(base_equity, 2),
            "components": "全球股指(50%) + A股(20%) + 新兴(15%) + 科技(15%)",
            "rationale": f"风险得分{risk_score:.0f}/100 → 权益仓位{base_equity:.0%}",
        },
        "gold": {
            "weight": round(gold_weight, 2),
            "components": "实物黄金ETF + 金矿股",
            "rationale": f"去美元化+VIX高→黄金对冲{gold_weight:.0%}",
        },
        "bonds": {
            "weight": round(bond_weight, 2),
            "components": "短期国债(50%) + TIPS(30%) + 中国国债(20%)",
            "rationale": "曲线倒挂→短端优于长端",
        },
        "cash": {
            "weight": 0.05,
            "components": "美元+人民币",
            "rationale": "保持流动性应对极端场景",
        },
    }
    
    # ── 视角交叉验证 ──
    cross_validations = []

    # 矛盾1：叙事看多 vs 系统承压
    if bull_ratio > 0.7 and system.get("phase_transition", {}).get("as_ratio", 0) > 1.2:
        cross_validations.append(
            "⚠️ 视角矛盾：叙事极度看多，但系统动力A/S比偏高 → 乐观可能是盲目的"
        )

    # 矛盾2：压力测试 vs 周期评分
    if n_alerts >= 5 and "低" in cycle.get("risk", ""):
        cross_validations.append(
            "⚠️ 视角矛盾：压力测试多场景告警，但周期评分偏乐观 → 可能低估尾部风险"
        )

    # 矛盾3：帝国衰落信号 vs 风险资产高配
    empire_stage = cycle.get("empire", {}).get("stage", "")
    if ("泡沫" in empire_stage or "冲突" in empire_stage or "更替" in empire_stage) and base_equity > 0.35:
        cross_validations.append(
            "⚠️ 视角矛盾：帝国周期处于" + empire_stage + "，权益仓位" + f"{base_equity:.0%}" + " → 帝国末期权益通常跑输"
        )

    # 矛盾4：金价暴涨 vs 风险评分温和
    # 从 historical_diff 或直接检测 gold YoY
    from engine.cycle_locator import diagnose
    try:
        lt_signals = diagnose().get("long_term", {}).get("signals", {})
        gold_signal = lt_signals.get("gold_yr", "")
        if "暴涨" in gold_signal and risk_score < 40:
            cross_validations.append(
                "⚠️ 视角矛盾：金价年涨" + gold_signal + "但综合风险仅" + f"{risk_score:.0f}/100 → 市场在用脚投票，模型可能滞后"
            )
    except:
        pass

    # 矛盾5：曲线深度倒挂 vs 权益高配
    yield_curve_val = 0
    try:
        import sqlite3
        db = sqlite3.connect("/home/xxxsuli/macro-engine/macro.db")
        c = db.execute("SELECT value FROM macro_indicators WHERE indicator_name='us_yield_curve' ORDER BY date DESC LIMIT 1")
        row = c.fetchone()
        if row: yield_curve_val = row[0]
        db.close()
    except:
        pass
    if yield_curve_val < 0.88 and base_equity > 0.40:
        cross_validations.append(
            "⚠️ 视角矛盾：收益率曲线深度倒挂(" + f"{yield_curve_val:.3f}" + ")，历史规律衰退概率>80%，但权益仓位" + f"{base_equity:.0%} → 曲线倒挂是前置指标，仓位应更防御"
        )

    # 矛盾6：历史类比「比历史更危险」vs 风险评分中性
    worse_count = diff.get("worse_count", 0)
    better_count = diff.get("better_count", 0)
    if worse_count > better_count * 2 and risk_score < 50:
        cross_validations.append(
            "⚠️ 视角矛盾：历史差异分析「比历史更危险」(" + str(worse_count) + ":" + str(better_count) + ")，但风险评分仅" + f"{risk_score:.0f} → 结构性恶化尚未反映在综合评分中"
        )

    # 一致1：多视角指向高风险
    if risk_score > 50 and n_alerts >= 4 and collapse_prob > 0.10:
        cross_validations.append(
            "🔴 视角一致：周期+压力+系统动力均指向高风险 → 高确信度"
        )

    # 一致2：多视角指向低风险
    if risk_score < 25 and n_alerts <= 2 and collapse_prob < 0.05:
        cross_validations.append(
            "🟢 视角一致：周期+压力+系统动力均指向低风险 → 正常配置"
        )

    # 一致3：历史+因果同向
    tm = template.get("top_matches", [{}])[0] if not template.get("error") else {}
    if tm.get("similarity", 0) > 0.35 and causal.get("n_triggers", 0) >= 3:
        cross_validations.append(
            "🔴 视角一致：历史类比(" + f"{tm.get('similarity',0)*100:.0f}%)" + " 与因果链条(" + str(causal.get("n_triggers", 0)) + "触发)指向同类风险 → 提高确信度"
        )
    
    return {
        "risk_score": round(risk_score, 1),
        "risk_reward": risk_reward,
        "scenarios": scenarios_probs,
        "allocation": allocation,
        "cross_validations": cross_validations,
        "phase": results.get("detected_phase", "normal_growth"),
        "phase_label": PHASE_WEIGHTS.get(results.get("detected_phase", "normal_growth"), {}).get("label", "正常增长期"),
    }


# ═══════════════════════════════════════════════════════
#  主流水线
# ═══════════════════════════════════════════════════════

def run_full_pipeline(skip_narrative_crawl: bool = True) -> dict:
    """执行 Dalio 6步完整分析流程。
    
    Args:
        skip_narrative_crawl: True 跳过新闻爬取（Web环境用）
    
    Returns:
        完整的综合诊断报告
    """
    results = {}
    errors = []
    today = date.today().isoformat()
    
    # ── Step 1: 模板匹配 ──
    try:
        results["template"] = step1_template_matching()
    except Exception as e:
        errors.append(f"Step1 模板匹配: {e}")
        results["template"] = {"error": str(e)}
    
    # ── Step 2: 周期定位 ──
    try:
        results["cycle"] = step2_cycle_positioning()
    except Exception as e:
        errors.append(f"Step2 周期: {e}")
        results["cycle"] = {"error": str(e)}
    
    # ── Step 3: 因果推演 ──
    try:
        results["causal"] = step3_causal_inference()
    except Exception as e:
        errors.append(f"Step3 因果: {e}")
        results["causal"] = {"error": str(e)}
    
    # ── Step 4: 博弈 ──
    try:
        results["game_theory"] = step4_game_theory()
    except Exception as e:
        errors.append(f"Step4 博弈: {e}")
        results["game_theory"] = {"error": str(e)}
    
    # ── Step 5: 压力测试 ──
    try:
        results["stress"] = step5_stress_test()
    except Exception as e:
        errors.append(f"Step5 压力: {e}")
        results["stress"] = {"error": str(e)}
    
    # ── 补充模块 ──
    try:
        from engine.narrative_v2 import run_narrative_v2
        results["narrative_full"] = run_narrative_v2(skip_crawl=skip_narrative_crawl)
    except Exception as e:
        results["narrative_full"] = {"error": str(e)}
    
    try:
        from engine.system_dynamics_v2 import analyze_v2 as sd2
        results["system_dynamics"] = sd2()
    except Exception as e:
        results["system_dynamics"] = {"error": str(e)}
    
    try:
        from engine.first_principles import analyze as fp
        results["first_principles"] = fp()
    except Exception as e:
        results["first_principles"] = {"error": str(e)}

    try:
        from engine.divergence_detector import detect_all as detect_divergence
        results["divergence"] = detect_divergence()
    except Exception as e:
        results["divergence"] = {"error": str(e)}
    
    # ── 检测宏观阶段 — V2 连续权重 ──
    ms = results["narrative_full"].get("media_sentiment", {})
    stress_alerts = results.get("stress", {}).get("n_alerts", 0)
    
    # V1 (保留兼容)
    detected_phase = detect_macro_phase(
        results["cycle"],
        ms,
        results.get("system_dynamics", {})
    )
    
    # V2 连续打分 + 模糊融合
    v2_phase, v2_label, v2_score, v2_weights, v2_phase_scores = detect_macro_phase_v2(
        results["cycle"], ms, results.get("system_dynamics", {}), stress_alerts
    )
    
    results["detected_phase"] = detected_phase
    results["v2_phase"] = v2_phase
    results["v2_phase_label"] = v2_label
    results["v2_phase_score"] = round(v2_score, 3)
    results["v2_phase_scores"] = {k: round(v, 3) for k, v in v2_phase_scores.items()}
    
    phase_info = PHASE_WEIGHTS.get(detected_phase, PHASE_WEIGHTS["normal_growth"])
    # 使用 V2 融合权重（平滑连续），而非 V1 离散权重
    phase_weights = v2_weights
    results["phase_info"] = phase_info
    results["active_weights"] = phase_weights
    results["active_weights_v1"] = phase_info.get("weights", DEFAULT_WEIGHTS)  # 保留V1对比
    
    # ── Step 6: 综合 ──
    try:
        results["synthesis"] = step6_synthesis(results, phase_weights)
    except Exception as e:
        errors.append(f"Step6 综合: {e}")
        results["synthesis"] = {"error": str(e)}

    # ── Step 6b: 贝叶斯三角验证 (增强层) ──
    try:
        from engine.bayesian_orchestrator import bayesian_integrate, bayesian_to_json
        bayesian_result = bayesian_integrate(results)
        results["synthesis"]["bayesian"] = bayesian_to_json(bayesian_result)
        # Use Bayesian risk score as primary if available
        results["synthesis"]["risk_score_bayesian"] = bayesian_result.risk_score
        results["synthesis"]["confidence"] = bayesian_result.confidence
        results["synthesis"]["entropy"] = bayesian_result.entropy
    except Exception as e:
        errors.append(f"Step6b 贝叶斯融合: {e}")
    
    # ── 总结 ──
    syn = results.get("synthesis", {})
    risk = syn.get("risk_score", 50)
    
    if risk > 70:
        overall = "🔴 高度警惕 — 多视角一致指向高风险，建议大幅防御"
    elif risk > 45:
        overall = "🟠 谨慎 — 部分视角严重告警，建议降低风险敞口+增持对冲"
    elif risk > 30:
        overall = "🟡 保持警惕 — 多信号预警，建议适度对冲"
    elif risk > 15:
        overall = "🟢 正常配置 — 风险可控，但需关注尾部风险"
    else:
        overall = "🟢 乐观 — 多视角一致向好"
    
    return {
        "date": today,
        "detected_phase": detected_phase,
        "phase_label": phase_info.get("label", "?"),
        "phase_description": phase_info.get("description", ""),
        "phase_info": phase_info,
        "active_weights": phase_weights,
        "overall_assessment": overall,
        "errors": errors,
        "results": results,
    }


# ═══════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dalio 6步协同总指挥")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    parser.add_argument("--full", action="store_true", help="完整详细输出（含各模块详情）")
    parser.add_argument("--live-narrative", action="store_true", help="实时爬取新闻（默认跳过）")
    args = parser.parse_args()
    
    print(f"\n🔮 Dalio 协同总指挥 — 6步分析流水线")
    print(f"   {date.today()}")
    print()
    
    result = run_full_pipeline(skip_narrative_crawl=not args.live_narrative)
    
    # Phase
    print(f"📍 宏观阶段: {result['phase_label']}")
    print(f"   {result['phase_description']}")
    print()
    
    # Steps summary
    r = result["results"]
    print("═══ 6步流水线 ═══")
    
    tpl = r.get("template", {})
    if not tpl.get("error"):
        m = tpl.get("top_matches", [{}])[0]
        print(f"  Step1 模板: {m.get('name','?')} ({m.get('similarity',0)*100:.0f}%) → {tpl.get('diff_analysis',{}).get('net_assessment','?')}")
    else:
        print(f"  Step1 模板: ⚠️ {tpl['error']}")
    
    cyc = r.get("cycle", {})
    if not cyc.get("error"):
        st = cyc.get("short_term", {}).get("stage", "?")
        lt = cyc.get("long_term", {}).get("stage", "?")
        print(f"  Step2 周期: 短期={st} | 长期={lt} | 风险={cyc.get('risk','?')}")
    
    cau = r.get("causal", {})
    if not cau.get("error"):
        print(f"  Step3 因果: {cau.get('n_triggers',0)}链触发 → {cau.get('n_future',0)}未来节点")
    
    gt = r.get("game_theory", {})
    if not gt.get("error"):
        tree = gt.get("game_tree", {})
        print(f"  Step4 博弈: {tree.get('net_trajectory','?')[:60]}")
    
    st = r.get("stress", {})
    if not st.get("error"):
        print(f"  Step5 压力: {st.get('n_alerts',0)}场景>20% | 极端{st.get('extreme_count',0)} 高危{st.get('high_count',0)}")
    
    syn = r.get("synthesis", {})
    if not syn.get("error"):
        print(f"  Step6 综合: 风险得分={syn.get('risk_score',0):.0f}/100 | {syn.get('risk_reward','?')}")
    
    print(f"\n═══ 动态权重 ({result['detected_phase']}) ═══")
    weights = result.get("active_weights", {})
    for k, w in sorted(weights.items(), key=lambda x: -x[1]):
        name = {"cycle":"周期","causal":"因果","template":"历史","stress":"压力",
                "game":"博弈","narrative":"叙事","system":"系统","first_principles":"第一性"}
        bar = "█" * int(w * 30) + "░" * (30 - int(w * 30))
        print(f"  {name.get(k,k):<8s} {w:.0%} {bar}")
    
    # Overall
    print(f"\n═══ 总判 ═══")
    print(f"  {result['overall_assessment']}")
    
    # 交叉验证
    if syn and not syn.get("error"):
        if syn.get("cross_validations"):
            print(f"\n  🔗 视角交叉验证:")
            for cv in syn["cross_validations"]:
                print(f"  {cv}")
        
        # 仓位
        print(f"\n═══ 仓位建议 ═══")
        alloc = syn.get("allocation", {})
        for asset, detail in alloc.items():
            w = detail["weight"]
            bar = "█" * int(w * 30) + "░" * (30 - int(w * 30))
            print(f"  {asset.upper():<6s} {w:.0%} {bar}")
            print(f"         {detail['components']}")
    
    # Errors
    if result.get("errors"):
        print(f"\n  ⚠️ 错误: {'; '.join(result['errors'])}")
    
    print()
    
    if args.json:
        output = {
            "date": result["date"],
            "phase": result["detected_phase"],
            "phase_label": result["phase_label"],
            "overall": result["overall_assessment"],
            "weights": result["active_weights"],
            "synthesis": r.get("synthesis", {}),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
