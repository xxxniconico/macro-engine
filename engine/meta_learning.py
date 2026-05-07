"""
meta_learning.py — 自适应模块可靠性 (Empirical Bayes)
=====================================================
让贝叶斯融合自动学习每个模块在不同宏观阶段的可靠性。

核心:
  P(phase|all) ∝ Π P(sᵢ|phase)^αᵢ(phase) × P(phase)
                                     ↑
                         α[module][phase] = 该模块在该阶段的经验精度

方法:
  1. 用 29 个历史危机模板作为"真相"标签
  2. 每个模板运行 8 个模块的似然函数
  3. 构建混淆矩阵: module × predicted_phase × actual_phase
  4. 拉普拉斯平滑 → 可靠性指数
  5. 持久化到 JSON，持续更新

输出: reliability_matrix.json (alpha exponents)
"""

import json
import math
import sqlite3
from pathlib import Path
from datetime import date
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

PROJ_ROOT = Path(__file__).parent.parent
DB_PATH = PROJ_ROOT / "macro.db"
MATRIX_PATH = PROJ_ROOT / "reliability_matrix.json"

PHASES = ['normal_growth', 'bubble_forming', 'crisis_unfolding', 'deleveraging', 'order_transition']
PHASE_LABELS_CN = {
    'normal_growth': '正常增长', 'bubble_forming': '泡沫形成',
    'crisis_unfolding': '危机爆发', 'deleveraging': '去杠杆', 'order_transition': '秩序更替'
}
MODULE_NAMES = ['cycle', 'causal', 'game_theory', 'stress', 'narrative', 'system', 'first_principles', 'template']

# ── Historical templates with ground truth phase labels ──────────
# (name, date, true_phase)
HISTORICAL_LABELS = [
    ("1929 Wall St Crash",     "1929-10-28", "crisis_unfolding"),
    ("1930s Great Depression", "1931-06-01", "deleveraging"),
    ("1942 WWII",              "1942-01-01", "order_transition"),
    ("1973 Oil Crisis",        "1973-10-17", "crisis_unfolding"),
    ("1979 Volcker Shock",     "1979-10-06", "deleveraging"),
    ("1987 Black Monday",      "1987-10-19", "crisis_unfolding"),
    ("1990 Japan Bubble",      "1990-01-01", "deleveraging"),
    ("1997 Asian Financial",   "1997-07-02", "crisis_unfolding"),
    ("1998 LTCM/Russia",       "1998-08-17", "crisis_unfolding"),
    ("2000 Dot-com Peak",      "2000-03-10", "bubble_forming"),
    ("2001 9/11",              "2001-09-11", "crisis_unfolding"),
    ("2008 GFC (Lehman)",      "2008-09-15", "crisis_unfolding"),
    ("2010 EU Sovereign Debt", "2010-05-02", "crisis_unfolding"),
    ("2013 Taper Tantrum",     "2013-06-19", "bubble_forming"),
    ("2014 Oil Crash",         "2014-12-01", "crisis_unfolding"),
    ("2015 China Stock Crash", "2015-08-24", "crisis_unfolding"),
    ("2018 Q4 Selloff",        "2018-12-24", "crisis_unfolding"),
    ("2020 COVID Crash",       "2020-03-16", "crisis_unfolding"),
    ("2022 Russia-Ukraine",    "2022-02-24", "crisis_unfolding"),
    ("2023 SVB Collapse",      "2023-03-10", "crisis_unfolding"),
    ("2024 Aug VIX Spike",     "2024-08-05", "crisis_unfolding"),
    # Normal periods (for contrast)
    ("2017 Mid-cycle",         "2017-06-01", "normal_growth"),
    ("2019 Pre-COVID",         "2019-12-01", "normal_growth"),
    ("2005 Housing Boom",      "2005-06-01", "bubble_forming"),
    ("1995 Mid-expansion",     "1995-06-01", "normal_growth"),
]


# ═══════════════════════════════════════════════════════════════
# Simplified module likelihoods for backtesting
# (Same logic as bayesian_orchestrator.py but self-contained)
# ═══════════════════════════════════════════════════════════════

def _get_features_at_date(db: sqlite3.Connection, cutoff: str) -> dict:
    """Extract key features from DB at a given date."""
    features = {}
    rows = db.execute('''
        SELECT indicator_name, MAX(date), value FROM macro_indicators
        WHERE date <= ? GROUP BY indicator_name
    ''', (cutoff,)).fetchall()
    for name, _, val in rows:
        features[name] = val
    return features


def _phase_from_features(features: dict, module: str) -> Dict[str, float]:
    """Simplified phase likelihood for backtesting (matches bayesian_orchestrator logic)."""
    likelihood = {p: 1.0 for p in PHASES}

    if module == 'cycle':
        # Use available indicators to infer cycle stage
        pmi = features.get('us_pmi', 50)
        cpi = features.get('us_cpi', 2)
        debt = features.get('us_debt_gdp', 100)
        reserve = features.get('usd_reserve_share', 60)
        polar = features.get('us_political_polarization', 0.5)

        if pmi < 45:
            likelihood['crisis_unfolding'] *= 3.0
            likelihood['deleveraging'] *= 2.0
            likelihood['normal_growth'] *= 0.3
        elif pmi > 55:
            likelihood['normal_growth'] *= 2.5

        if cpi > 5:
            likelihood['deleveraging'] *= 2.5
            likelihood['bubble_forming'] *= 1.5
        elif cpi < 1:
            likelihood['crisis_unfolding'] *= 1.5

        if debt > 110:
            likelihood['deleveraging'] *= 3.0
            likelihood['normal_growth'] *= 0.3
        if reserve < 58:
            likelihood['order_transition'] *= 2.5
        if polar > 0.7:
            likelihood['order_transition'] *= 2.0

    elif module == 'causal':
        vix = features.get('us_vixy', 20)
        curve = features.get('us_yield_curve', 1.0)
        gold_yr = features.get('gold_1y_reference', 0)

        if vix > 30:
            likelihood['crisis_unfolding'] *= 4.0
            likelihood['normal_growth'] *= 0.1
        elif vix > 25:
            likelihood['crisis_unfolding'] *= 2.5
            likelihood['deleveraging'] *= 1.5

        if curve < 0.9:
            likelihood['crisis_unfolding'] *= 3.0
            likelihood['deleveraging'] *= 2.0
            likelihood['normal_growth'] *= 0.2

        if gold_yr > 25:
            likelihood['deleveraging'] *= 2.5
            likelihood['crisis_unfolding'] *= 2.0

    elif module == 'game_theory':
        fed_rate = features.get('us_fed_rate', 3)
        curve = features.get('us_yield_curve', 1.0)

        if curve < 0.95:
            likelihood['deleveraging'] *= 2.5
            likelihood['crisis_unfolding'] *= 1.5
            likelihood['normal_growth'] *= 0.3
        if fed_rate > 5:
            likelihood['bubble_forming'] *= 2.0
        elif fed_rate < 1:
            likelihood['crisis_unfolding'] *= 1.5
            likelihood['deleveraging'] *= 1.5

    elif module == 'stress':
        vix = features.get('us_vixy', 20)
        credit = features.get('credit_spread', 1.5)
        gpr = features.get('geopolitical_risk', 100)

        if vix > 35:
            likelihood['crisis_unfolding'] *= 5.0
            likelihood['normal_growth'] *= 0.05
        elif vix > 25:
            likelihood['crisis_unfolding'] *= 2.5
            likelihood['deleveraging'] *= 1.5

        if credit > 3.0:
            likelihood['crisis_unfolding'] *= 3.0
            likelihood['deleveraging'] *= 2.0

        if gpr > 150:
            likelihood['order_transition'] *= 2.0
            likelihood['crisis_unfolding'] *= 1.5

    elif module == 'narrative':
        # No sentiment data in DB → use VIX as sentiment proxy
        vix = features.get('us_vixy', 20)
        sp500 = features.get('us_sp500', 3000)
        debt = features.get('us_debt_gdp', 100)

        if vix > 30:
            likelihood['crisis_unfolding'] *= 3.0
            likelihood['normal_growth'] *= 0.15
        elif vix < 15:
            likelihood['normal_growth'] *= 2.5
            if debt > 100:
                likelihood['bubble_forming'] *= 1.5

    elif module == 'system':
        pmi = features.get('us_pmi', 50)
        debt = features.get('us_debt_gdp', 100)
        reserve = features.get('usd_reserve_share', 60)

        if pmi < 45 and debt > 100:
            likelihood['crisis_unfolding'] *= 3.0
            likelihood['deleveraging'] *= 2.5
            likelihood['normal_growth'] *= 0.1
        elif pmi > 55 and reserve > 58:
            likelihood['normal_growth'] *= 3.0
        elif reserve < 55:
            likelihood['order_transition'] *= 2.5
            likelihood['deleveraging'] *= 1.5

    elif module == 'first_principles':
        debt = features.get('us_debt_gdp', 100)
        curve = features.get('us_yield_curve', 1.0)
        reserve = features.get('usd_reserve_share', 60)

        if debt > 120 and curve < 0.95:
            likelihood['deleveraging'] *= 4.0
            likelihood['normal_growth'] *= 0.1
        if reserve < 55:
            likelihood['order_transition'] *= 2.5
        if curve > 1.5:
            likelihood['bubble_forming'] *= 2.0

    elif module == 'template':
        # Historical templates: conservative → equal weight unless strong signal
        vix = features.get('us_vixy', 20)
        if vix > 35:
            likelihood['crisis_unfolding'] *= 2.0

    # Normalize
    total = sum(likelihood.values())
    if total > 0:
        likelihood = {p: v/total for p, v in likelihood.items()}
    return likelihood


# ═══════════════════════════════════════════════════════════════
# Meta-Learning: Calibration & Reliability Estimation
# ═══════════════════════════════════════════════════════════════

def calibrate_reliability(db_path: str = None, save: bool = True) -> Dict[str, Dict[str, float]]:
    """
    Run backtest across historical templates to estimate:
    α[module][phase] = P(correct | module top-prediction, true phase)

    Uses Laplace (add-1) smoothing.

    Returns reliability matrix: {module: {phase: alpha}}
    """
    db_path = db_path or str(DB_PATH)
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA busy_timeout=5000")

    # ── Confusion accumulator: module → predicted_phase → true_phase → count
    confusion = {
        mod: {pred: {true: 0 for true in PHASES} for pred in PHASES}
        for mod in MODULE_NAMES
    }

    results = []
    n_tested = 0

    for name, crisis_date, true_phase in HISTORICAL_LABELS:
        features = _get_features_at_date(db, crisis_date)
        n_features = len(features)

        if n_features < 5:
            continue  # Not enough data

        n_tested += 1
        template_result = {'name': name, 'date': crisis_date, 'true_phase': true_phase, 'modules': {}}

        for mod in MODULE_NAMES:
            likelihood = _phase_from_features(features, mod)
            predicted = max(likelihood, key=likelihood.get)
            prob = likelihood[predicted]

            # Accumulate confusion
            confusion[mod][predicted][true_phase] += 1

            template_result['modules'][mod] = {
                'predicted': predicted,
                'prob': round(prob, 3),
                'correct': predicted == true_phase,
            }

        results.append(template_result)

    db.close()

    # ── Compute reliability: α[mod][phase] ──
    # alpha = P(predicted_correctly | true_phase) / P(random_chance)
    # Using Laplace smoothing: (count_correct + 1) / (total_attempts + n_phases)
    reliability = {}
    for mod in MODULE_NAMES:
        reliability[mod] = {}
        for true_p in PHASES:
            total_attempts = sum(confusion[mod][pred][true_p] for pred in PHASES)
            correct = confusion[mod][true_p][true_p]  # predicted == true
            alpha = (correct + 1) / (total_attempts + len(PHASES)) if total_attempts > 0 else 0.2
            reliability[mod][true_p] = round(alpha, 3)

    # ── Print report ──
    print(f"\n🧠 Meta-Learning Calibration ({n_tested} templates)")
    print("=" * 70)
    print(f"{'Module':<20s} {'正常':>6s} {'泡沫':>6s} {'危机':>6s} {'去杠杆':>6s} {'秩序':>6s}  {'Avg':>6s}")
    print("-" * 70)

    for mod in MODULE_NAMES:
        vals = [reliability[mod][p] for p in PHASES]
        avg = sum(vals) / len(vals)
        row = f"{mod:<20s}"
        for v in vals:
            bar = '★' if v > 0.4 else '▸' if v > 0.25 else '·'
            row += f" {bar}{v:.2f}"
        row += f"  {avg:.3f}"
        print(row)

    print()

    # ── Per-template accuracy ──
    hits = defaultdict(int)
    total = defaultdict(int)
    for r in results:
        for mod, info in r['modules'].items():
            total[mod] += 1
            if info['correct']:
                hits[mod] += 1

    print("Per-module raw accuracy:")
    for mod in MODULE_NAMES:
        acc = hits[mod] / max(total[mod], 1) * 100
        bar = '█' * int(acc / 5)
        print(f"  {mod:<20s} {acc:5.1f}% {bar} ({hits[mod]}/{total[mod]})")

    # ── Save ──
    if save:
        output = {
            "calibrated_at": date.today().isoformat(),
            "n_templates": n_tested,
            "reliability": reliability,
            "per_module_accuracy": {
                mod: round(hits[mod] / max(total[mod], 1), 3) for mod in MODULE_NAMES
            },
            "phase_coverage": {
                p: sum(1 for r in results if r['true_phase'] == p) for p in PHASES
            },
        }
        with open(MATRIX_PATH, 'w') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n📁 Reliability matrix saved: {MATRIX_PATH}")

    return reliability


def load_reliability() -> Dict[str, Dict[str, float]]:
    """Load saved reliability matrix, or return default (all 1.0)."""
    if MATRIX_PATH.exists():
        with open(MATRIX_PATH) as f:
            data = json.load(f)
            return data.get('reliability', {})
    # Default: equal reliability
    return {mod: {p: 1.0 for p in PHASES} for mod in MODULE_NAMES}


# ═══════════════════════════════════════════════════════════════
# Integration: fuse with reliability weights
# ═══════════════════════════════════════════════════════════════

def fuse_bayesian_with_reliability(
    module_likelihoods: Dict[str, Dict[str, float]],
    prior: Dict[str, float] = None,
    reliability: Dict[str, Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Bayesian fusion with per-module-per-phase reliability exponents.

    P(phase|all) ∝ Π P(sᵢ|phase)^αᵢ(phase) × P(phase)

    α[module][phase] < 1 → downweight unreliable modules in that phase
    α[module][phase] > 1 → upweight reliable modules in that phase
    """
    if prior is None:
        from engine.bayesian_orchestrator import PRIOR
        prior = PRIOR

    if reliability is None:
        reliability = load_reliability()

    log_posterior = {}
    for phase in PHASES:
        log_p = math.log(max(prior.get(phase, 0.05), 1e-10))
        for mod_name, likelihood in module_likelihoods.items():
            alpha = reliability.get(mod_name, {}).get(phase, 1.0)
            # Clamp alpha: don't let unreliable modules get zero weight
            alpha = max(0.1, min(2.0, alpha))
            l_val = max(likelihood.get(phase, 1e-10), 1e-10)
            log_p += alpha * math.log(l_val)
        log_posterior[phase] = log_p

    # Normalize
    from engine.bayesian_orchestrator import log_sum_exp
    log_norm = log_sum_exp(list(log_posterior.values()))
    posterior = {p: math.exp(v - log_norm) for p, v in log_posterior.items()}
    return posterior


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(PROJ_ROOT))

    # 1. Calibrate
    print("📐 Calibrating module reliability from historical templates...")
    reliability = calibrate_reliability(save=True)

    # 2. Compare: with vs without reliability weights
    print("\n" + "=" * 70)
    print("📊 A/B Test: Bayesian fusion with vs without reliability weights")
    print("=" * 70)

    from engine.bayesian_orchestrator import (
        fuse_bayesian, cycle_likelihood, causal_likelihood,
        game_theory_likelihood, stress_likelihood, narrative_likelihood,
        system_dynamics_likelihood, first_principles_likelihood, template_likelihood,
    )
    from engine.orchestrator import run_full_pipeline

    orch = run_full_pipeline(skip_narrative_crawl=True)
    r = orch.get('results', {})

    # Get likelihoods from current state
    module_liks = {
        'cycle': cycle_likelihood(r.get('cycle', {})),
        'causal': causal_likelihood(r.get('causal', {})),
        'game_theory': game_theory_likelihood(r.get('game_theory', {})),
        'stress': stress_likelihood(r.get('stress', {})),
        'narrative': narrative_likelihood(r.get('narrative_full', r.get('narrative', {}))),
        'system': system_dynamics_likelihood(r.get('system_dynamics', {})),
        'first_principles': first_principles_likelihood(r.get('first_principles', {})),
        'template': template_likelihood(r.get('template', {})),
    }

    # Without reliability (all α=1)
    result_no_meta = fuse_bayesian(
        module_liks['cycle'], module_liks['causal'], module_liks['game_theory'],
        module_liks['stress'], module_liks['narrative'], module_liks['system'],
        module_liks['first_principles'], module_liks['template'],
    )

    # With reliability
    posterior_meta = fuse_bayesian_with_reliability(module_liks, reliability=reliability)

    print("\nPosterior comparison:")
    print(f"{'Phase':<20s} {'No Meta':>10s} {'With Meta':>10s} {'Δ':>8s}")
    print("-" * 50)
    for p in PHASES:
        b = result_no_meta.posterior.get(p, 0)
        a = posterior_meta.get(p, 0)
        d = a - b
        arrow = '↑' if d > 0.02 else '↓' if d < -0.02 else '→'
        print(f"  {p:<20s} {b*100:>8.1f}% {a*100:>8.1f}% {arrow} {d*100:>+5.1f}%")

    risk_no = sum(result_no_meta.posterior[p] * result_no_meta.PHASE_RISK_BASELINE.get(p, 50) for p in PHASES)
    risk_meta = sum(posterior_meta[p] * result_no_meta.PHASE_RISK_BASELINE.get(p, 50) for p in PHASES)

    print(f"\n  Risk (no meta): {risk_no:.1f}")
    print(f"  Risk (meta):    {risk_meta:.1f}")
    print(f"  Δ risk:         {risk_meta - risk_no:+.1f}")
