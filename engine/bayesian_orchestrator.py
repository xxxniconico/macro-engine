"""
bayesian_orchestrator.py — 贝叶斯三角验证层
=============================================
替代 orchestrator.py 中的加权平均，实现 Dalio 方法论中
真正的 triangulation：每个模块输出条件概率分布，
贝叶斯融合为统一后验，天然量化不确定性。

核心公式:
  P(phase | all_signals) ∝ Πᵢ P(signalᵢ | phase) × P(phase)

输出:
  - posterior: 5 相概率分布
  - entropy: 不确定性量化 (0=确定, 1.6=完全不确定)
  - confidence_interval: 风险得分 ± 范围
  - divergence_map: 哪些模块打架了
"""

import math
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

PHASES = ['normal_growth', 'bubble_forming', 'crisis_unfolding', 'deleveraging', 'order_transition']
PHASE_LABELS = {
    'normal_growth': '正常增长', 'bubble_forming': '泡沫形成',
    'crisis_unfolding': '危机爆发', 'deleveraging': '去杠杆', 'order_transition': '秩序更替'
}
PHASE_RISK_BASELINE = {
    'normal_growth': 20, 'bubble_forming': 45, 'crisis_unfolding': 75,
    'deleveraging': 65, 'order_transition': 55
}

# Prior from historical base rates (~120yr of US data)
PRIOR = {
    'normal_growth': 0.40,      # Most common state
    'bubble_forming': 0.15,
    'crisis_unfolding': 0.12,   # Crises are rare
    'deleveraging': 0.20,       # Long deleveraging phases
    'order_transition': 0.13,   # Rare but multi-decade
}

# ═══════════════════════════════════════════════════════════════
# Module → Phase Likelihood Functions
# ═══════════════════════════════════════════════════════════════

def cycle_likelihood(cycle_results: dict) -> Dict[str, float]:
    """
    P(signal_cycle | phase)
    Maps the cycle locator's 3-dimension output to 5-phase likelihoods.
    """
    short = cycle_results.get('short_term', {})
    long = cycle_results.get('long_term', {})
    empire = cycle_results.get('empire', {})

    s_stage = short.get('stage', '')
    l_stage = long.get('stage', '')
    e_stage = empire.get('stage', '')

    likelihood = {p: 1.0 for p in PHASES}  # Start neutral

    # Short-term cycle → phase
    if '衰退' in s_stage or 'contraction' in s_stage.lower():
        likelihood['crisis_unfolding'] *= 3.5
        likelihood['deleveraging'] *= 2.0
        likelihood['normal_growth'] *= 0.2
    elif '过热' in s_stage or 'overheat' in s_stage.lower():
        likelihood['bubble_forming'] *= 3.0
        likelihood['normal_growth'] *= 0.3
    elif '扩张' in s_stage or 'expansion' in s_stage.lower():
        likelihood['normal_growth'] *= 2.5
        likelihood['bubble_forming'] *= 1.5
    elif '筑底' in s_stage or 'bottom' in s_stage.lower():
        likelihood['deleveraging'] *= 2.0
        likelihood['crisis_unfolding'] *= 1.5

    # Long-term debt cycle → phase
    if '去杠杆' in l_stage or 'deleverag' in l_stage.lower():
        likelihood['deleveraging'] *= 4.0
        likelihood['normal_growth'] *= 0.15
        likelihood['crisis_unfolding'] *= 2.0
    elif '泡沫' in l_stage or 'bubble' in l_stage.lower():
        likelihood['bubble_forming'] *= 3.0
    elif '正常' in l_stage or 'normal' in l_stage.lower():
        likelihood['normal_growth'] *= 2.0

    # Empire cycle → phase
    if '内部冲突' in e_stage or '冲突' in e_stage:
        likelihood['order_transition'] *= 5.0
        likelihood['normal_growth'] *= 0.1
    elif '泡沫' in e_stage:
        likelihood['order_transition'] *= 3.0
        likelihood['bubble_forming'] *= 2.0
    elif '秩序' in e_stage or '更替' in e_stage:
        likelihood['order_transition'] *= 4.0
        likelihood['deleveraging'] *= 2.0

    # Normalize
    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def causal_likelihood(causal_results: dict) -> Dict[str, float]:
    """
    P(signal_causal | phase)
    Causal chains triggered → which phase they point to.
    """
    n_triggers = causal_results.get('n_triggers', 0)
    n_approaching = causal_results.get('n_approaching', 0)
    events = causal_results.get('future_events', causal_results.get('events', []))

    likelihood = {p: 1.0 for p in PHASES}

    # Count events by domain as phase signal
    phase_signals = defaultdict(float)
    for evt in events:
        nid = evt.get('node_id', evt.get('id', ''))
        if any(w in nid for w in ['default', 'debt_crisis', 'bank', 'credit', 'deleverage']):
            phase_signals['deleveraging'] += 1
        elif any(w in nid for w in ['recession', 'crash', 'crisis', 'contagion', 'turmoil']):
            phase_signals['crisis_unfolding'] += 1
        elif any(w in nid for w in ['bubble', 'speculation', 'overheat', 'mania']):
            phase_signals['bubble_forming'] += 1
        elif any(w in nid for w in ['order', 'reserve', 'transition', 'polarization', 'conflict']):
            phase_signals['order_transition'] += 1

    total_signals = sum(phase_signals.values()) or 1
    for p in PHASES:
        signal_strength = phase_signals.get(p, 0) / total_signals
        likelihood[p] *= (1.0 + signal_strength * 3.0)

    # Trigger count → crisis/deleveraging signal
    if n_triggers >= 5:
        likelihood['crisis_unfolding'] *= 3.0
        likelihood['deleveraging'] *= 2.0
        likelihood['normal_growth'] *= 0.1
    elif n_triggers >= 3:
        likelihood['crisis_unfolding'] *= 2.0
        likelihood['deleveraging'] *= 1.5
        likelihood['normal_growth'] *= 0.3
    else:
        likelihood['normal_growth'] *= 2.0

    # Approaching triggers → bubble/warning
    if n_approaching >= 3:
        likelihood['bubble_forming'] *= 2.0
        likelihood['normal_growth'] *= 0.5

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def game_theory_likelihood(game_results: dict) -> Dict[str, float]:
    """
    P(signal_game | phase)
    What players are doing → what phase that implies.
    """
    trajectory = game_results.get('trajectory', '')
    scenarios = game_results.get('scenarios', [])
    tree = game_results.get('game_tree', {})

    likelihood = {p: 1.0 for p in PHASES}

    # Trajectory keywords
    traj_lower = trajectory.lower()
    if 'crisis' in traj_lower or 'turmoil' in traj_lower or 'crash' in traj_lower:
        likelihood['crisis_unfolding'] *= 4.0
        likelihood['normal_growth'] *= 0.1
    if 'cut' in traj_lower or 'easing' in traj_lower or '宽松' in trajectory:
        likelihood['deleveraging'] *= 2.5
        likelihood['crisis_unfolding'] *= 1.5
        likelihood['normal_growth'] *= 0.3
    if 'tighten' in traj_lower or 'hike' in traj_lower or '紧缩' in trajectory:
        likelihood['bubble_forming'] *= 2.0
    if 'stable' in traj_lower or 'growth' in traj_lower:
        likelihood['normal_growth'] *= 3.0

    # Terminal scenarios — count crisis vs benign
    n_crisis = sum(1 for s in scenarios if any(w in s.get('label','').lower()
        for w in ['crisis','crash','default','turmoil','war']))
    if n_crisis >= 2:
        likelihood['crisis_unfolding'] *= 3.0
        likelihood['normal_growth'] *= 0.2

    # Check game tree rounds for Fed/PBoC behavior
    rounds = tree.get('rounds', [])
    for rnd in rounds:
        for move in rnd.get('moves', []):
            move_str = str(move).lower()
            if 'fed' in move_str and 'cut' in move_str:
                likelihood['deleveraging'] *= 1.5
            if 'pbc' in move_str and 'stimulus' in move_str:
                likelihood['deleveraging'] *= 1.3

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def stress_likelihood(stress_results: dict) -> Dict[str, float]:
    """
    P(signal_stress | phase)
    Stress scenario probabilities → phase mapping.
    """
    n_alerts = stress_results.get('n_alerts', 0)
    top_risks = stress_results.get('top_risks', [])

    likelihood = {p: 1.0 for p in PHASES}

    if n_alerts >= 8:
        likelihood['crisis_unfolding'] *= 5.0
        likelihood['deleveraging'] *= 3.0
        likelihood['normal_growth'] *= 0.05
    elif n_alerts >= 5:
        likelihood['crisis_unfolding'] *= 3.0
        likelihood['deleveraging'] *= 2.0
        likelihood['normal_growth'] *= 0.2
    elif n_alerts >= 2:
        likelihood['crisis_unfolding'] *= 1.5
        likelihood['bubble_forming'] *= 1.3
        likelihood['normal_growth'] *= 0.6
    else:
        likelihood['normal_growth'] *= 3.0

    # Classify top risks by phase
    for risk in top_risks[:5]:
        rid = risk.get('id', risk.get('scenario_id', ''))
        if any(w in rid for w in ['debt','default','deleverage','credit']):
            likelihood['deleveraging'] *= 1.5
        if any(w in rid for w in ['war','conflict','geopolitical','transition']):
            likelihood['order_transition'] *= 1.5
        if any(w in rid for w in ['recession','crash','liquidity','turmoil']):
            likelihood['crisis_unfolding'] *= 1.5
        if any(w in rid for w in ['bubble','speculation','asset']):
            likelihood['bubble_forming'] *= 1.5

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def narrative_likelihood(narrative_results: dict) -> Dict[str, float]:
    """
    P(signal_narrative | phase)
    Market sentiment → phase signal.
    """
    bull = narrative_results.get('bull_ratio', 0.5)
    tipping = narrative_results.get('tipping_risk', 'normal')
    divergence = narrative_results.get('divergence_score', 0)

    likelihood = {p: 1.0 for p in PHASES}

    if bull > 0.85:
        likelihood['bubble_forming'] *= 4.0
        likelihood['normal_growth'] *= 0.2
    elif bull > 0.70:
        likelihood['bubble_forming'] *= 2.5
        likelihood['normal_growth'] *= 1.5
    elif bull < 0.15:
        likelihood['crisis_unfolding'] *= 3.0
        likelihood['deleveraging'] *= 2.0
        likelihood['normal_growth'] *= 0.15
    elif bull < 0.30:
        likelihood['crisis_unfolding'] *= 1.8
        likelihood['deleveraging'] *= 1.5
        likelihood['normal_growth'] *= 0.4
    else:
        likelihood['normal_growth'] *= 2.0

    if tipping == 'high' or tipping == 'extreme':
        likelihood['crisis_unfolding'] *= 1.5
        likelihood['bubble_forming'] *= 1.5

    if divergence > 0.15:
        likelihood['crisis_unfolding'] *= 1.8  # Narrative divergence = regime change
        likelihood['order_transition'] *= 1.3

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def system_dynamics_likelihood(sd_results: dict) -> Dict[str, float]:
    """
    P(signal_system | phase)
    Stabilizer/amplifier ratio → phase signal.
    """
    criticality = sd_results.get('criticality', 'stable')
    pt = sd_results.get('phase_transition', {})

    likelihood = {p: 1.0 for p in PHASES}

    if 'critical' in criticality.lower() or '危急' in criticality:
        likelihood['crisis_unfolding'] *= 4.0
        likelihood['deleveraging'] *= 3.0
        likelihood['normal_growth'] *= 0.05
    elif 'warning' in criticality.lower() or '警告' in criticality:
        likelihood['crisis_unfolding'] *= 2.0
        likelihood['bubble_forming'] *= 1.5
        likelihood['normal_growth'] *= 0.3
    else:
        likelihood['normal_growth'] *= 2.5

    # Phase transition danger
    if pt.get('collapse_prob', 0) > 0.15:
        likelihood['crisis_unfolding'] *= 3.0
        likelihood['normal_growth'] *= 0.1

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def first_principles_likelihood(fp_results: dict) -> Dict[str, float]:
    """
    P(signal_fp | phase)
    First principles chains → which natural laws are actively violating equilibrium.
    """
    chains = fp_results.get('active_chains', [])
    summary = fp_results.get('summary', '')

    likelihood = {p: 1.0 for p in PHASES}

    # Count chain activations by direction
    for chain in chains:
        cid = chain.get('id', chain.get('chain_id', ''))
        strength = chain.get('strength', chain.get('score', 0.5))
        if 'debt' in cid or 'credit' in cid:
            likelihood['deleveraging'] *= (1 + strength)
        if 'bubble' in cid or 'speculation' in cid:
            likelihood['bubble_forming'] *= (1 + strength)
        if 'war' in cid or 'conflict' in cid or 'order' in cid:
            likelihood['order_transition'] *= (1 + strength)
        if 'recession' in cid or 'contraction' in cid:
            likelihood['crisis_unfolding'] *= (1 + strength)

    if 'imminent' in summary.lower() or '迫在眉睫' in summary:
        for p in PHASES:
            if p != 'normal_growth':
                likelihood[p] *= 1.3

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


def template_likelihood(template_results: dict) -> Dict[str, float]:
    """
    P(signal_template | phase)
    Historical templates → which phase the best-matching crisis belongs to.
    """
    top_match = template_results.get('top_match', {})
    tm = template_results.get('top_matches', [{}])[0] if not top_match else top_match
    diff = template_results.get('diff', template_results.get('diff_analysis', {}))

    likelihood = {p: 1.0 for p in PHASES}

    name = (tm.get('name') or '').lower()
    similarity = tm.get('similarity', 0)

    if similarity < 0.1:
        # No strong match → stay close to prior
        total = sum(likelihood.values())
        return {p: v/total for p, v in likelihood.items()}

    # Map historical crisis to phase
    if any(w in name for w in ['deleverag', 'gfc', '2008', 'credit', 'debt', 'default']):
        likelihood['deleveraging'] *= (1 + similarity * 3)
    elif any(w in name for w in ['crash', 'crisis', 'turmoil', 'panic']):
        likelihood['crisis_unfolding'] *= (1 + similarity * 3)
    elif any(w in name for w in ['bubble', 'dot-com', 'peak']):
        likelihood['bubble_forming'] *= (1 + similarity * 3)
    elif any(w in name for w in ['war', 'conflict', 'order']):
        likelihood['order_transition'] *= (1 + similarity * 3)

    # "比历史更危险" → amplify negative phases
    net = diff.get('net_assessment', '') if isinstance(diff, dict) else str(diff)
    if '更危险' in net or 'worse' in net.lower():
        likelihood['deleveraging'] *= 1.5
        likelihood['crisis_unfolding'] *= 1.5
        likelihood['normal_growth'] *= 0.3

    total = sum(likelihood.values())
    return {p: v/total for p, v in likelihood.items()}


# ═══════════════════════════════════════════════════════════════
# Bayesian Fusion Engine
# ═══════════════════════════════════════════════════════════════

@dataclass
class BayesianResult:
    """Output of the Bayesian fusion."""
    posterior: Dict[str, float]        # P(phase | all_signals)
    posterior_probs: Dict[str, float]  # Same, alias
    entropy: float                     # Shannon entropy (0 = certain, ~1.6 = max uncertainty)
    entropy_max: float                 # max possible entropy for reference
    confidence: str                    # 'high' | 'medium' | 'low' | 'very_low'
    risk_score: float                  # Expected risk score: Σ P(phase) × risk_baseline(phase)
    risk_ci: Tuple[float, float]      # 50% credible interval
    top_phase: str                     # Most likely phase
    top_phase_prob: float              # Probability of most likely phase
    divergence: List[dict]             # Which module pairs disagree most
    individual_likelihoods: Dict[str, Dict[str, float]]  # Per-module distributions
    module_weights: Dict[str, float]   # Effective weight each module had (based on KL from prior)
    narrative: str                     # Human-readable synthesis


def log_sum_exp(values: List[float]) -> float:
    """Numerically stable log-sum-exp."""
    if not values:
        return float('-inf')
    max_val = max(values)
    return max_val + math.log(sum(math.exp(v - max_val) for v in values))


def shannon_entropy(probs: Dict[str, float]) -> float:
    """H = -Σ p_i log₂(p_i) — 0 = certainty, log₂(n) = max uncertainty."""
    ent = 0.0
    for p in probs.values():
        if p > 0:
            ent -= p * math.log2(p)
    return ent


def kl_divergence(p: Dict[str, float], q: Dict[str, float]) -> float:
    """KL(P||Q) — how much information P adds relative to prior Q."""
    kl = 0.0
    for phase in PHASES:
        if p.get(phase, 0) > 0 and q.get(phase, 0) > 0:
            kl += p[phase] * math.log2(p[phase] / q[phase])
    return kl


def fuse_bayesian(
    cycle_lik: Dict[str, float],
    causal_lik: Dict[str, float],
    game_lik: Dict[str, float],
    stress_lik: Dict[str, float],
    narrative_lik: Dict[str, float],
    system_lik: Dict[str, float],
    fp_lik: Dict[str, float],
    template_lik: Dict[str, float],
    prior: Dict[str, float] = None,
    reliability: Dict[str, float] = None,
    meta_reliability: Dict[str, Dict[str, float]] = None,
) -> BayesianResult:
    """
    Bayesian fusion: P(phase | all) ∝ Πᵢ P(sᵢ | phase) × P(phase)

    Uses log-space for numerical stability. Each module's likelihood is
    tempered by its per-phase reliability from meta-learning calibration.

    When meta_reliability is provided (from meta_learning.py),
    α[module][phase] < 1 downweights unreliable modules in that phase,
    α[module][phase] > 1 upweights reliable modules.
    """
    prior = prior or PRIOR

    # Load reliability matrix if available
    if meta_reliability is None:
        try:
            from engine.meta_learning import load_reliability
            meta_reliability = load_reliability()
        except:
            meta_reliability = {}

    # Module names and their likelihoods
    modules_info = [
        ('cycle', cycle_lik, '周期定位'),
        ('causal', causal_lik, '因果推理'),
        ('game_theory', game_lik, '博弈论'),
        ('stress', stress_lik, '压力测试'),
        ('narrative', narrative_lik, '叙事分析'),
        ('system', system_lik, '系统动力'),
        ('first_principles', fp_lik, '第一性原理'),
        ('template', template_lik, '历史模板'),
    ]

    # Default reliability: all modules equally weighted
    if reliability is None:
        reliability = {m[0]: 1.0 for m in modules_info}

    # ── Log-space Bayesian update with meta-learning weights ──
    log_posterior = {}
    for phase in PHASES:
        log_p = math.log(max(prior[phase], 1e-10))
        for mod_name, lik, _ in modules_info:
            # Use per-phase reliability from meta-learning, or flat reliability, or 1.0
            if meta_reliability and mod_name in meta_reliability:
                alpha = meta_reliability[mod_name].get(phase, 1.0)
            else:
                alpha = reliability.get(mod_name, 1.0) if reliability else 1.0
            # Clamp: don't let any module get zero weight or dominate
            alpha = max(0.1, min(2.5, alpha))
            l_val = max(lik.get(phase, 1e-10), 1e-10)
            log_p += alpha * math.log(l_val)
        log_posterior[phase] = log_p

    # Normalize (log-sum-exp trick)
    log_norm = log_sum_exp(list(log_posterior.values()))
    posterior = {p: math.exp(v - log_norm) for p, v in log_posterior.items()}

    # ── Entropy & Confidence ──
    ent = shannon_entropy(posterior)
    ent_max = math.log2(len(PHASES))  # ~2.32 for 5 phases
    normalized_entropy = ent / ent_max if ent_max > 0 else 0

    if normalized_entropy < 0.35:
        confidence = 'high'
    elif normalized_entropy < 0.55:
        confidence = 'medium'
    elif normalized_entropy < 0.75:
        confidence = 'low'
    else:
        confidence = 'very_low'

    # ── Risk Score: expected value ──
    risk_score = sum(posterior[p] * PHASE_RISK_BASELINE[p] for p in PHASES)

    # ── 50% Credible Interval ──
    sorted_phases = sorted(PHASES, key=lambda p: posterior[p], reverse=True)
    cum = 0
    ci_phases = []
    for p in sorted_phases:
        cum += posterior[p]
        ci_phases.append(p)
        if cum >= 0.5:
            break
    ci_scores = [PHASE_RISK_BASELINE[p] for p in ci_phases]
    risk_ci = (min(ci_scores), max(ci_scores))

    # ── Top Phase ──
    top_phase = max(posterior, key=posterior.get)
    top_prob = posterior[top_phase]

    # ── Module Divergence Detection ──
    # Compare each module's top phase vs consensus
    divergence = []
    for mod_name, lik, label in modules_info:
        mod_top = max(lik, key=lik.get)
        mod_top_prob = lik[mod_top]
        if mod_top != top_phase and mod_top_prob > 0.25:
            divergence.append({
                'module': label,
                'module_top': mod_top,
                'module_top_label': PHASE_LABELS.get(mod_top, mod_top),
                'module_prob': round(mod_top_prob * 100, 1),
                'consensus_top': top_phase,
                'consensus_top_label': PHASE_LABELS.get(top_phase, top_phase),
                'severity': 'high' if mod_top_prob > 0.40 else 'medium',
            })

    # ── Effective Module Weights (KL from prior) ──
    module_weights = {}
    for mod_name, lik, _ in modules_info:
        kl = kl_divergence(lik, prior)
        module_weights[mod_name] = round(min(1.0, kl / max(1.0, kl)), 3)

    # ── Narrative ──
    risk_label = '🟢 安全' if risk_score < 30 else '🟡 警惕' if risk_score < 45 else '🟠 谨慎' if risk_score < 60 else '🔴 危险' if risk_score < 80 else '💀 极端'
    div_text = ''
    if divergence:
        div_names = [d['module'] for d in divergence[:3]]
        div_text = f' — {",".join(div_names)}分歧'

    narrative = (
        f"{risk_label} · 风险 {risk_score:.0f}/100 ±{int((risk_ci[1]-risk_ci[0])/2)} "
        f"· 确信度 {confidence} "
        f"· {PHASE_LABELS[top_phase]}主导 ({top_prob*100:.0f}%)"
        f"{div_text}"
    )

    return BayesianResult(
        posterior=posterior,
        posterior_probs=posterior,
        entropy=round(ent, 3),
        entropy_max=round(ent_max, 3),
        confidence=confidence,
        risk_score=round(risk_score, 1),
        risk_ci=risk_ci,
        top_phase=top_phase,
        top_phase_prob=round(top_prob, 3),
        divergence=divergence,
        individual_likelihoods={m[0]: m[1] for m in modules_info},
        module_weights=module_weights,
        narrative=narrative,
    )


# ═══════════════════════════════════════════════════════════════
# Integration: hook into existing orchestrator
# ═══════════════════════════════════════════════════════════════

def bayesian_integrate(orchestrator_results: dict) -> BayesianResult:
    """
    Takes the full orchestrator output dict (results from each step)
    and runs Bayesian fusion on top of it.

    Usage in orchestrator.py step6_synthesis():
        from bayesian_orchestrator import bayesian_integrate
        bresult = bayesian_integrate(results)
        synthesis['risk_score'] = bresult.risk_score
        synthesis['bayesian'] = bresult.__dict__
    """
    r = orchestrator_results

    # Extract per-module results
    cyc = r.get('cycle', {})
    cau = r.get('causal', {})
    gt = r.get('game_theory', {})
    st = r.get('stress', {})
    nv = r.get('narrative_full', r.get('narrative', {}))
    sd = r.get('system_dynamics', {})
    fp = r.get('first_principles', {})
    tpl = r.get('template', {})

    # Compute likelihoods
    cycle_lik = cycle_likelihood(cyc)
    causal_lik = causal_likelihood(cau)
    game_lik = game_theory_likelihood(gt)
    stress_lik = stress_likelihood(st)
    narrative_lik = narrative_likelihood(nv)
    system_lik = system_dynamics_likelihood(sd)
    fp_lik = first_principles_likelihood(fp)
    tpl_lik = template_likelihood(tpl)

    # Fuse
    result = fuse_bayesian(
        cycle_lik, causal_lik, game_lik, stress_lik,
        narrative_lik, system_lik, fp_lik, tpl_lik,
    )

    return result


# ═══════════════════════════════════════════════════════════════
# Export: convert to JSON-safe dict for dashboard
# ═══════════════════════════════════════════════════════════════

def bayesian_to_json(result: BayesianResult) -> dict:
    """Convert BayesianResult to JSON-serializable dict for data.json."""
    return {
        'posterior': {PHASE_LABELS.get(p, p): round(v, 4) for p, v in result.posterior.items()},
        'entropy': result.entropy,
        'entropy_max': result.entropy_max,
        'confidence': result.confidence,
        'risk_score': result.risk_score,
        'risk_ci': list(result.risk_ci),
        'top_phase': result.top_phase,
        'top_phase_label': PHASE_LABELS.get(result.top_phase, result.top_phase),
        'top_phase_prob': result.top_phase_prob,
        'divergence': result.divergence,
        'narrative': result.narrative,
        'module_weights': result.module_weights,
    }
