"""Streamlit 看板 V7 — Dalio 协同总指挥 + 全模块。"""

import sys, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

from data.storage import get_indicator_count, get_snapshot

st.set_page_config(page_title="Dalio 宏观协同总指挥", page_icon="🔮", layout="wide")
st.title("🔮 Dalio 宏观协同总指挥 V7")
st.caption("6步分析流程 + 动态视角加权 + 仓位建议 | 8大视角协同决策")

# ═══ 刷新 ═══
if st.button("🔄 刷新诊断", type="primary"):
    with st.spinner("抓取数据 + 运行引擎..."):
        import subprocess
        subprocess.run(["bash", str(Path(__file__).parent.parent / "run_daily.sh")],
                       capture_output=True, timeout=90)
    st.rerun()

# ═══ 总指挥面板 ═══
from engine.orchestrator import run_full_pipeline, PHASE_WEIGHTS

with st.spinner("运行 6步协同流水线..."):
    orch = run_full_pipeline(skip_narrative_crawl=True)

syn = orch.get("results", {}).get("synthesis", {})

# 一行：阶段 + 风险 + 总判
c1, c2, c3 = st.columns(3)
with c1:
    phase_icon = {"normal_growth":"🟢","bubble_forming":"🟡","crisis_unfolding":"🔴",
                  "deleveraging":"🟠","order_transition":"💀"}.get(orch["detected_phase"], "⚪")
    st.metric("宏观阶段", f"{phase_icon} {orch['phase_label']}", orch["phase_description"][:50])
with c2:
    risk_score = syn.get("risk_score", 50)
    risk_color = "🟢" if risk_score < 30 else ("🟡" if risk_score < 45 else ("🟠" if risk_score < 65 else "🔴"))
    st.metric("综合风险得分", f"{risk_color} {risk_score:.0f}/100", syn.get("risk_reward", "")[:30])
with c3:
    st.metric("总判", orch["overall_assessment"].split("—")[0] if "—" in orch["overall_assessment"] else orch["overall_assessment"][:30],
             orch["overall_assessment"].split("—")[1] if "—" in orch["overall_assessment"] else "")

# 交叉验证
if syn.get("cross_validations"):
    for cv in syn["cross_validations"]:
        if "🔴" in cv:
            st.error(cv)
        else:
            st.warning(cv)

# ═══ 动态权重 + 仓位 ═══
st.markdown("---")
cw1, cw2 = st.columns([1, 1.2])

with cw1:
    st.subheader("⚖️ 动态视角权重")
    weights = orch.get("active_weights", {})
    name_map = {"cycle":"周期定位","causal":"因果链条","template":"历史类比","stress":"压力测试",
                "game":"多方博弈","narrative":"叙事分析","system":"系统动力","first_principles":"第一性原理"}
    
    wdata = []
    for k, w in sorted(weights.items(), key=lambda x: -x[1]):
        wdata.append({"视角": name_map.get(k, k), "权重": w})
    
    if wdata:
        df_w = pd.DataFrame(wdata)
        fig_w = go.Figure()
        colors_w = ["#ff6b6b" if d["权重"] > 0.2 else "#ffd93d" if d["权重"] > 0.1 else "#6bcb77" for d in wdata]
        fig_w.add_trace(go.Bar(x=[d["权重"] for d in wdata], y=[d["视角"] for d in wdata],
                               orientation='h', marker_color=colors_w,
                               text=[f"{d['权重']:.0%}" for d in wdata], textposition='outside'))
        fig_w.update_layout(height=250, margin=dict(l=100, r=40, t=10, b=10),
                           xaxis=dict(range=[0, max(0.35, max(d["权重"] for d in wdata)*1.3)]),
                           showlegend=False)
        st.plotly_chart(fig_w, use_container_width=True)
    else:
        st.caption("权重未加载")

with cw2:
    st.subheader("💰 仓位建议")
    alloc = syn.get("allocation", {})
    for asset, detail in alloc.items():
        w = detail["weight"]
        bar_len = int(w * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        a_icon = {"equity":"📈","gold":"🥇","bonds":"📜","cash":"💵"}.get(asset, "📦")
        st.caption(f"{a_icon} **{asset.upper()}** `{w:.0%}` {bar}")
        st.caption(f"  ↳ {detail['components']}")

# ═══ 6步摘要 ═══
st.markdown("---")
st.subheader("📋 6步流水线摘要")
r = orch.get("results", {})

sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
tpl = r.get("template", {})
m = tpl.get("top_matches", [{}])[0] if tpl.get("top_matches") else {}
with sc1:
    st.metric("1️⃣ 模板", f"{m.get('name','?')[:12]}", f"{m.get('similarity',0)*100:.0f}%")

cyc = r.get("cycle", {})
with sc2:
    st.metric("2️⃣ 周期", cyc.get("short_term",{}).get("stage","?")[:8], cyc.get("risk","?"))

cau = r.get("causal", {})
with sc3:
    st.metric("3️⃣ 因果", f"{cau.get('n_triggers',0)}链触发", f"{cau.get('n_future',0)}未来节点")

gt = r.get("game_theory", {})
tree = gt.get("game_tree", {})
with sc4:
    st.metric("4️⃣ 博弈", tree.get("net_trajectory","?")[:15])

st_data = r.get("stress", {})
with sc5:
    st.metric("5️⃣ 压力", f"{st_data.get('n_alerts',0)}告警", f"{st_data.get('n_scenarios',0)}场景")

with sc6:
    st.metric("6️⃣ 综合", f"风险{syn.get('risk_score',50):.0f}", syn.get("risk_reward","?")[:10])

# ═══ 详细模块 ═══
st.markdown("---")
st.subheader("📊 详细模块")

# 复用总指挥的结果
result = orch.get("results", {}).get("cycle", diagnose())
match_list = orch.get("results", {}).get("template", {}).get("top_matches", [])
match_result = {
    "matches": match_list if isinstance(match_list, list) else [],
    "available_features": 18,
    "total_features": 18,
    "path_prediction": orch.get("results", {}).get("template", {}).get("path_prediction", {}),
}

c1, c2, c3 = st.columns(3)

for col, key, label, thresh in [
    (c1, "short_term", "短期债务周期", 0.2),
    (c2, "long_term", "长期债务周期", 0.2),
    (c3, "empire", "帝国/秩序周期", 0),
]:
    cyc = result[key]
    color = "🟢" if cyc["score"] > thresh else ("🟡" if cyc["score"] > -0.3 else "🔴")
    with col:
        st.metric(label, f"{color} {cyc['stage']}", f"置信度 {cyc['confidence']:.0%}")
        for k, v in cyc.get("signals", {}).items():
            st.caption(f"• {k}: {v}")

# ═══ 风险 ═══
st.markdown("---")
risk = result["risk"]
if "高" in risk: st.error("🔴 高风险 — 三周期中至少两个处于危险区间")
elif "中" in risk: st.warning("🟡 中等风险 — 一个周期处于危险区间")
else: st.success("🟢 低风险 — 所有周期处于正常区间")

# ═══ 历史模板匹配 ═══
st.markdown("---")
st.subheader("🔍 历史模板匹配 (29 模板·6 危机类型)")
st.caption(f"余弦相似度 | 可用特征 {match_result['available_features']}/{match_result['total_features']}")

if match_result.get("message"):
    st.warning(match_result["message"])
else:
    cols = st.columns(min(5, len(match_result["matches"])))
    for i, m in enumerate(match_result["matches"]):
        with cols[i]:
            sim_pct = m["similarity"] * 100
            color = "#1a8a1a" if sim_pct > 70 else ("#d4a800" if sim_pct > 40 else "#cc3333")
            st.markdown(f"""
            <div style="background:#1e1e2e;border-left:4px solid {color};border-radius:8px;padding:10px;margin-bottom:6px;">
                <strong>#{i+1}</strong> <span style="color:{color}">{sim_pct:.1f}%</span><br>
                <small>{m['name']}</small><br>
                <small style="color:#888">{m.get('crisis_type','')}</small><br>
                <small style="color:#888">{m['country']} | {m['period']}</small>
            </div>
            """, unsafe_allow_html=True)

    # 相似度柱状图
    names = [m["name"] for m in match_result["matches"]]
    sims = [m["similarity"] * 100 for m in match_result["matches"]]
    colors = ["#1a8a1a" if s > 70 else ("#d4a800" if s > 40 else "#cc3333") for s in sims]
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=sims, y=names, orientation='h', marker_color=colors,
                              text=[f"{s:.1f}%" for s in sims], textposition='outside'))
    fig_bar.update_layout(height=220, margin=dict(l=200, r=40, t=0, b=0),
                           xaxis=dict(range=[0, max(sims)*1.3]), showlegend=False)
    st.plotly_chart(fig_bar, use_container_width=True)

# ═══ 路径预测 ═══
st.markdown("---")
st.subheader("🔮 前瞻推演：路径预测")
pp = match_result.get("path_prediction", {})
if pp and pp.get("dominant_type"):
    dt = pp["dominant_type"]
    st.info(f"**主导危机类型：{dt}** | 基于 Top5 匹配相似度加权")

    pcols = st.columns(3)
    for i, h in enumerate(["6m", "12m", "24m"]):
        with pcols[i]:
            st.metric(f"{h} 后", pp.get(h, "N/A").replace("[主导] ", "").replace("[次] ", ""))
    
    with st.expander("📖 历史匹配详情"):
        for i, m in enumerate(match_result["matches"]):
            st.markdown(f"**#{i+1} {m['name']}** ({m['similarity']*100:.1f}% · {m.get('crisis_type','')})")
            st.caption(m["outcome"])
            if m.get("path"):
                st.caption(f"→ 6m: {m['path'].get('6m','?')} | 12m: {m['path'].get('12m','?')} | 24m: {m['path'].get('24m','?')}")
            st.markdown("---")
else:
    st.caption("无路径预测数据")

# ═══ 数据覆盖 ═══
st.markdown("---")
st.subheader("📦 数据覆盖")
st.text(f"{get_indicator_count()}种指标 | 短期/长期/帝国 100% | 新浪V5 + World Bank + 东方财富")

# ═══ 因果链条 ═══
st.markdown("---")
st.subheader("⛓️ 因果链条推演")
from engine.causal_chain import detect_triggers, traverse as causal_traverse, CAUSAL_GRAPH
triggers = detect_triggers()
if triggers:
    st.info(f"**已触发种子事件：** {', '.join(CAUSAL_GRAPH[t]['label'] for t in triggers)}")
    timeline = causal_traverse(triggers)
    future_events = [e for e in timeline if e["expected_month"] > 0]
    if future_events:
        for e in future_events[:8]:
            chain_str = " → ".join(CAUSAL_GRAPH.get(n, {}).get("label", n) for n in e["chain"])
            st.markdown(f"`T+{e['expected_month']:<4}` **{e['label']}**  ← {chain_str}")
    else:
        st.caption("当前触发事件尚无下游传导")
else:
    st.caption("当前无已触发因果链种子事件")

# ═══ 压力测试 V2 — 公式化概率 ═══
st.markdown("---")
st.subheader("⚠️ 反向压力测试 V2 (公式化概率)")

try:
    from engine.stress_test_v2 import evaluate_all_scenarios, get_active_alerts
    st_v2 = evaluate_all_scenarios()
    alerts = get_active_alerts(st_v2, 0.20)
    extreme_count = sum(1 for r in st_v2 if r["probability"] > 0.65)
    high_count = sum(1 for r in st_v2 if 0.40 < r["probability"] <= 0.65)
    elevated_count = sum(1 for r in st_v2 if 0.20 < r["probability"] <= 0.40)
    
    st.caption(f"28场景 | 💀={extreme_count} 🔴={high_count} 🟡={elevated_count} | {len(alerts)}个场景需关注")
    
    cols = st.columns(4)
    for i, s in enumerate(st_v2[:12]):
        with cols[i % 4]:
            bar = "█" * int(s["probability"] * 20)
            st.markdown(f"""
            <div style="background:#1e1e2e;border-left:4px solid {'#ff4444' if s['probability']>0.4 else '#d4a800'};border-radius:8px;padding:10px;margin-bottom:8px;">
                <strong>{s['risk_level'][:2]} {s['label']}</strong><br>
                <span style="font-size:1.2em">{s['probability']:.1%}</span><br>
                <small style="color:#888">{s.get('description','')[:60]}...</small>
            </div>
            """, unsafe_allow_html=True)
    
    if alerts:
        with st.expander("🔍 详细概率分解"):
            for r in alerts[:5]:
                st.markdown(f"**{r['label']}** — 综合 P={r['probability']:.1%}")
                for pc in r.get("preconditions", []):
                    st.caption(f"  · {pc['key']} {pc['op']} {pc['threshold']} → 独立P={pc['probability']:.0%} (实际={pc['value']})")
except Exception as e:
    st.warning(f"V2 压力测试引擎错误: {e}")
    # 回退
    from engine.stress_test import monitor as stress_monitor
    stress = stress_monitor()
    sorted_stress = sorted(stress.values(), key=lambda x: x["activation_pct"], reverse=True)
    for i, s in enumerate(sorted_stress[:12]):
        with cols[i % 4]:
            st.markdown(f"{s['label']}: {s['activation_pct']}%")

# ═══ P2: 叙事 + 博弈 + 系统动力 ═══
st.markdown("---")
st.subheader("🧠 P2: 叙事·博弈·系统动力")

tab_n, tab_g, tab_s = st.tabs(["📰 叙事分析", "🎯 多方博弈", "🔄 系统动力"])

with tab_n:
    try:
        from engine.narrative_v2 import run_narrative_v2
        nv2 = run_narrative_v2(skip_crawl=False)
        ms = nv2["media_sentiment"]
        
        # 情绪仪表
        c1, c2, c3 = st.columns(3)
        with c1:
            bar_icon = "🟢" if ms["bull_ratio"] > 0.6 else ("🔴" if ms["bull_ratio"] < 0.4 else "🟡")
            st.metric("牛熊比", f"{bar_icon} {ms['bull_ratio']:.0%}", f"有效情绪 {ms['bullish']+ms['bearish']}/{ms['total']}条")
        with c2:
            st.metric("情绪分", f"{ms['sentiment_score']:+.2f}", "-1恐慌 ~ +1贪")
        with c3:
            st.metric("中性率", f"{ms.get('neutral_ratio',0):.0%}", f"{ms['neutral']}条无明确倾向")
        
        # 转折点告警
        tp = nv2["tipping_point"]
        if tp.get("is_extreme"):
            for sig in tp["signals"]:
                st.warning(sig)
        else:
            for sig in tp["signals"]:
                st.info(sig)
        
        # 背离分析
        dv = nv2["divergence"]
        if dv["divergences"]:
            st.error(f"⚠️ 叙事-数据背离 (得分={dv['divergence_score']})")
            for d in dv["divergences"]:
                st.caption(f"  {d}")
        
        # 情绪历史趋势
        if nv2["history"]:
            st.markdown("**近7天情绪趋势**")
            import pandas as pd
            df_sent = pd.DataFrame(nv2["history"])
            if not df_sent.empty and "bull_ratio" in df_sent.columns:
                st.line_chart(df_sent.set_index("date")["bull_ratio"], use_container_width=True)
        
        # 总结
        st.caption(f"📊 {nv2['summary']}")
        
    except Exception as e:
        st.warning(f"V2 叙事引擎错误: {e}，回退 V1")
        from engine.narrative import analyze as narrative_analyze
        narratives = narrative_analyze()
        for n in narratives[:6]:
            bar_len = int(n["strength"] * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            risk_icon = {"positive": "🟢", "warning": "🟡", "danger": "🔴"}.get(n["risk"], "⚪")
            st.markdown(f"{risk_icon} **{n['theme']}** `{n['strength']:.0%}` {bar}")
            with st.expander(f"详情: {n['theme']}"):
                st.caption(f"描述: {n['description']}")
                st.caption(f"⚠ 反转信号: {n['peak_signal']}")
                st.caption(f"💡 反叙事: {n['contra_narrative']}")

with tab_g:
    try:
        from engine.game_theory_v2 import analyze_v2 as game_v2, PLAYERS as GP
        gv = game_v2()
        
        # 博弈树摘要
        tree = gv["game_tree"]
        st.subheader("🌳 动态博弈树 (3步前瞻)")
        st.caption(f"**轨迹:** {tree['net_trajectory']}")
        
        # 各轮展示
        for r in tree["rounds"]:
            with st.expander(f"第{r['round']}轮 → SP500={r['state_snapshot']['SP500']} 黄金={r['state_snapshot']['黄金']} VIX={r['state_snapshot']['VIX']}"):
                for pid, move in r["moves"].items():
                    name = GP.get(pid, {}).get("name", pid)
                    impact = r["impacts"].get(pid, "")
                    st.caption(f"**{name}**: {move}")
                    if impact:
                        st.caption(f"  → {impact}")
        
        # 终局场景
        st.subheader("🎲 终局场景概率")
        cols = st.columns(min(4, len(tree["terminal_scenarios"])))
        for i, s in enumerate(tree["terminal_scenarios"]):
            with cols[i % 4]:
                st.metric(s["name"], f"{s['probability']:.0%}")
                st.caption(s["description"][:80])
        
        # 各方状态
        st.subheader("📋 参与方状态")
        for p in gv["players"]:
            st.metric(p["player"], f"{p['status']} · {p['bias']}")
        
        # 净效应
        with st.expander("⚖️ 博弈净效应"):
            for e in gv["net_effects"]:
                st.caption(e)
                
    except Exception as e:
        st.warning(f"V2 博弈引擎错误: {e}，回退 V1")
        from engine.game_theory import analyze as game_analyze, get_net_effects
        players = game_analyze()
        for p in players:
            st.metric(p["player"], f"{p['status']} · {p['bias']}")
        for e in get_net_effects():
            st.caption(e)

with tab_s:
    try:
        from engine.system_dynamics_v2 import analyze_v2 as sys_v2, LOOPS
        sd2 = sys_v2()
        
        # 系统状态 + 相变预警
        c1, c2 = st.columns(2)
        with c1:
            st.metric("系统状态", sd2["criticality"])
        with c2:
            pt = sd2["phase_transition"]
            st.metric("崩溃概率", f"{pt['systemic_collapse_probability']:.1%}",
                     f"A/S比={pt['as_ratio']} | 净健康={pt['net_health']}")
        
        # 相变警告
        for w in pt["warnings"]:
            if "🚨" in w or "🔴" in w:
                st.error(w)
            else:
                st.warning(w)
        
        # 稳定器健康度（量化）
        st.subheader("🛡️ 稳定器健康度")
        for lid, s in sd2["stabilizer_details"].items():
            bar_len = int(s["health_score"] / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            icon = "🟢" if s["health_score"] > 65 else ("🟡" if s["health_score"] > 35 else "🔴")
            st.caption(f"{icon} **{s['label']}** `{s['health_score']:.0f}` {bar} {'✅活跃' if s['active'] else '休眠'}")
            if s["failure_signals"]:
                for f in s["failure_signals"]:
                    st.caption(f"  ↳ {f}")
        
        # 回路相互作用
        if sd2["active_interactions"]:
            with st.expander("⚡ 活跃的回路相互作用"):
                for i in sd2["active_interactions"][:8]:
                    icon = {"amplify": "🔺", "dampen": "🔻", "compete": "⚔️", "trigger": "🔔"}.get(i["effect"], "→")
                    st.caption(f"{icon} [{i['strength']:.1f}] {i['description']}")
        
    except Exception as e:
        st.warning(f"V2 系统动力引擎错误: {e}，回退 V1")
        from engine.system_dynamics import analyze as sys_analyze
        sd = sys_analyze()
        st.metric("系统状态", sd["criticality"])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🔺 放大器**")
            for l in sd["active_positive"]:
                st.warning(f"⚠ {l['label']}: {l['description']}")
        with c2:
            st.markdown("**🛡️ 稳定器**")
            for s_loop in sd["all_stabilizers"]:
                health = s_loop.get("health", "unknown")
                icon = {"healthy": "🟢", "available": "🟡", "fragile": "🔴"}.get(health, "⚪")
                st.caption(f"{icon} {s_loop['label']}: {health}")
        if sd["n_pos"] >= 3 and sd["n_healthy_stabilizers"] < 2:
            st.error("🚨 Dalio最警惕：当稳定器失效，只剩放大器运行 = 系统性崩溃前兆")

# ═══ 图表 ═══
st.markdown("---")
conn = sqlite3.connect(str(Path(__file__).parent.parent / "macro.db"))
df_cn = pd.read_sql("SELECT date, value FROM macro_indicators WHERE indicator_name='china_gdp_growth' ORDER BY date", conn)
df_us = pd.read_sql("SELECT date, value FROM macro_indicators WHERE indicator_name='us_gdp_growth' ORDER BY date", conn)
df_gold = pd.read_sql("SELECT date, value FROM macro_indicators WHERE indicator_name='gold' ORDER BY date", conn)
conn.close()

tab1, tab2 = st.tabs(["GDP 中美对比", "黄金走势"])
with tab1:
    if not df_cn.empty and not df_us.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_cn["date"], y=df_cn["value"], name="中国GDP", line=dict(color="red")))
        fig.add_trace(go.Scatter(x=df_us["date"], y=df_us["value"], name="美国GDP", line=dict(color="blue")))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=350, title="中美GDP增速(1960-2024)", yaxis_title="%")
        st.plotly_chart(fig, use_container_width=True)
with tab2:
    if not df_gold.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_gold["date"], y=df_gold["value"], name="黄金$/oz", line=dict(color="gold")))
        fig.update_layout(height=350, title="黄金价格")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(f"最后更新: {date.today()} | V7 协同总指挥 | 8视角·6步流程·动态权重·仓位输出")
