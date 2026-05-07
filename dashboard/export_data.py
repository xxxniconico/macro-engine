"""数据导出器 — 为 HTML 看板生成完整 JSON 数据。

输出: dashboard/data.json
内容:
  - orchestrator: 总指挥完整输出
  - time_series: 所有关键指标的历史时序 (SQLite)
  - sentiment_history: 叙事情绪历史
  - stress_history: 压力测试历史
  - game_history: 博弈历史
"""

import json
import sqlite3
from pathlib import Path
from datetime import date, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

DB = Path(__file__).parent.parent / "macro.db"
OUTPUT = Path(__file__).parent / "data.json"


def export_time_series() -> dict:
    """导出所有指标的历史时间序列。"""
    conn = sqlite3.connect(str(DB))
    c = conn.cursor()
    
    series = {}
    
    # 按指标名分组，输出 {name: [{date, value}, ...]}
    c.execute("""
        SELECT indicator_name, date, value 
        FROM macro_indicators 
        WHERE indicator_name IN (
            'china_pmi', 'china_cpi', 'china_gdp_growth', 'china_sh_index',
            'china_debt_gdp', 'china_gini', 'china_unemployment',
            'us_sp500', 'us_cpi', 'us_gdp_growth', 'us_unemployment',
            'us_vixy', 'us_yield_curve', 'us_fed_rate', 'us_debt_gdp',
            'us_gini', 'usd_reserve_share', 'us_political_polarization',
            'us_wealth_gap', 'us_uso', 'us_tlt', 'us_spy', 'us_gld', 'us_shy',
            'us_real_rate',
            'gold', 'credit_spread', 'em_eem', 'us_pmi',
            'china_real_rate', 'china_military', 'china_education',
            'china_wealth_gap',
            'geopolitical_risk', 'us_epu', 'china_epu', 'global_shadow_banking',
            'us_rgdp_growth_lt', 'us_inflation_lt', 'us_stir_lt', 'us_ltrate_lt',
            'us_real_rate_lt', 'us_debtgdp_lt', 'us_eq_return_lt', 'us_housing_return_lt',
            'us_investment_gdp_lt', 'us_current_account_lt', 'us_unemployment_lt',
            'g7_inflation_lt', 'g7_debtgdp_lt'
        )
        ORDER BY indicator_name, date
    """)
    
    for name, dt, val in c.fetchall():
        if name not in series:
            series[name] = []
        series[name].append([dt, val])
    
    conn.close()
    return series


def export_sentiment_history() -> list:
    """导出叙事情绪历史。"""
    conn = sqlite3.connect(str(DB))
    c = conn.cursor()
    try:
        c.execute("""
            SELECT date, sentiment_score, bull_ratio, total_headlines, tipping_risk, divergence_score
            FROM sentiment_history ORDER BY date
        """)
        return [{"date": r[0], "sentiment_score": r[1], "bull_ratio": r[2],
                 "total_headlines": r[3], "tipping_risk": r[4], "divergence_score": r[5]}
                for r in c.fetchall()]
    except:
        return []
    finally:
        conn.close()


def export_stress_history() -> dict:
    """导出压力测试历史。"""
    conn = sqlite3.connect(str(DB))
    c = conn.cursor()
    try:
        c.execute("""
            SELECT date, scenario_id, probability, risk_level
            FROM stress_test_history ORDER BY date, scenario_id
        """)
        history = {}
        for dt, sid, prob, level in c.fetchall():
            if sid not in history:
                history[sid] = []
            history[sid].append({"date": dt, "probability": prob, "risk_level": level})
        return history
    except:
        return {}
    finally:
        conn.close()


def export_game_history() -> list:
    """导出博弈历史。"""
    conn = sqlite3.connect(str(DB))
    c = conn.cursor()
    try:
        c.execute("""
            SELECT date, player_id, status, bias, tension
            FROM game_history ORDER BY date
        """)
        return [{"date": r[0], "player": r[1], "status": r[2], "bias": r[3], "tension": r[4]}
                for r in c.fetchall()]
    except:
        return []
    finally:
        conn.close()


def main():
    print("📦 导出数据...")
    
    # 1. 总指挥
    print("  [1/5] 总指挥...")
    from engine.orchestrator import run_full_pipeline
    orch = run_full_pipeline(skip_narrative_crawl=True)
    
    # 去掉无法序列化的部分（Plotly对象等）
    orch_clean = {
        "date": orch["date"],
        "detected_phase": orch["detected_phase"],
        "phase_label": orch["phase_label"],
        "phase_description": orch["phase_description"],
        "overall_assessment": orch["overall_assessment"],
        "active_weights": orch.get("active_weights", {}),
        "v2_phase_scores": orch.get("results", {}).get("v2_phase_scores", {}),  # V2 连续阶段得分
        "errors": orch.get("errors", []),
    }
    
    # 精简 results
    r = orch.get("results", {})
    
    # Step1 模板
    tpl = r.get("template", {})
    orch_clean["template"] = {
        "top_match": (tpl.get("top_matches", [{}])[0] if tpl.get("top_matches") else {}),
        "diff": tpl.get("diff_analysis", {}).get("net_assessment", ""),
    }
    
    # Step2 周期
    cyc = r.get("cycle", {})
    orch_clean["cycle"] = {
        k: {"stage": cyc.get(k, {}).get("stage", ""), "score": cyc.get(k, {}).get("score", 0),
            "confidence": cyc.get(k, {}).get("confidence", 0),
            "signals": cyc.get(k, {}).get("signals", {})}
        for k in ["short_term", "long_term", "empire"]
    }
    orch_clean["cycle"]["risk"] = cyc.get("risk", "?")
    
    # Step3 因果
    cau = r.get("causal", {})
    orch_clean["causal"] = {
        "n_triggers": cau.get("n_triggers", 0),
        "n_approaching": cau.get("n_approaching", 0),
        "n_future": cau.get("n_future", 0),
        "active_triggers": cau.get("active_triggers", []),
        "approaching_triggers": cau.get("approaching_triggers", []),
        "events": cau.get("future_events", []),
    }
    
    # Step4 博弈
    gt = r.get("game_theory", {})
    tree = gt.get("game_tree", {})
    orch_clean["game_theory"] = {
        "trajectory": tree.get("net_trajectory", ""),
        "scenarios": tree.get("terminal_scenarios", []),
        "rounds": tree.get("rounds", []),
        "players": gt.get("players", []),
    }
    
    # Step5 压力
    st = r.get("stress", {})
    orch_clean["stress"] = {
        "n_alerts": st.get("n_alerts", 0),
        "n_scenarios": st.get("n_scenarios", 0),
        "top_risks": st.get("top_risks", [])[:8],
    }
    
    # Step6 综合
    syn = r.get("synthesis", {})
    orch_clean["synthesis"] = {
        "risk_score": syn.get("risk_score", 50),
        "risk_score_bayesian": syn.get("risk_score_bayesian", syn.get("risk_score", 50)),
        "confidence": syn.get("confidence", "medium"),
        "entropy": syn.get("entropy", 1.0),
        "risk_reward": syn.get("risk_reward", ""),
        "allocation": syn.get("allocation", {}),
        "cross_validations": syn.get("cross_validations", []),
        "bayesian": syn.get("bayesian", {}),
    }
    
    # 第一性原理
    fp = r.get("first_principles", {})
    orch_clean["first_principles"] = {
        "summary": fp.get("summary", ""),
        "active_chains": fp.get("active_chains", [])[:4],
    }
    
    # 系统动力
    sd = r.get("system_dynamics", {})
    orch_clean["system_dynamics"] = {
        "criticality": sd.get("criticality", ""),
        "phase_transition": sd.get("phase_transition", {}),
        "stabilizer_details": sd.get("stabilizer_details", {}),
        "active_interactions": sd.get("active_interactions", []),
        "all_interactions": sd.get("all_interactions", []),
    }
    
    # 叙事
    nv = r.get("narrative_full", {})
    orch_clean["narrative"] = {
        "bull_ratio": nv.get("media_sentiment", {}).get("bull_ratio", 0.5),
        "sentiment_score": nv.get("media_sentiment", {}).get("sentiment_score", 0),
        "tipping_risk": nv.get("tipping_point", {}).get("tipping_point_risk", "normal"),
        "divergence_score": nv.get("divergence", {}).get("divergence_score", 0),
    }

    # 背离检测
    div = r.get("divergence", {})
    orch_clean["divergence"] = {
        "summary": div.get("summary", ""),
        "n_critical": div.get("n_critical", 0),
        "n_warning": div.get("n_warning", 0),
        "divergences": div.get("divergences", []),
    }
    
    # 2. 时序
    print("  [2/5] 时间序列...")
    time_series = export_time_series()
    
    # 3. 情绪历史
    print("  [3/5] 情绪历史...")
    sentiment_history = export_sentiment_history()
    
    # 4. 压力历史
    print("  [4/5] 压力历史...")
    stress_history = export_stress_history()
    
    # 5. 博弈历史
    print("  [5/5] 博弈历史...")
    game_history = export_game_history()
    
    # 组装
    data = {
        "generated_at": date.today().isoformat(),
        "orchestrator": orch_clean,
        "time_series": time_series,
        "sentiment_history": sentiment_history,
        "stress_history": stress_history,
        "game_history": game_history,
    }
    
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    
    # 统计
    ts_count = sum(len(v) for v in time_series.values())
    print(f"\n✅ 导出完成: {OUTPUT}")
    print(f"   总指挥: ✓")
    print(f"   时间序列: {len(time_series)} 种指标, {ts_count} 条")
    print(f"   情绪历史: {len(sentiment_history)} 条")
    print(f"   压力历史: {sum(len(v) for v in stress_history.values())} 条")
    print(f"   博弈历史: {len(game_history)} 条")


if __name__ == "__main__":
    main()
