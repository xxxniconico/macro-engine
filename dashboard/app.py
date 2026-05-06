"""Streamlit 看板 V4 — Dalio 宏观周期定位 + 历史模板匹配 + 路径预测。"""

import sys, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

from engine.cycle_locator import diagnose
from engine.template_matcher import run_matcher, FEATURE_NAMES, predict_path
from data.storage import get_indicator_count, get_snapshot

st.set_page_config(page_title="Dalio 宏观周期定位", page_icon="📊", layout="wide")
st.title("📊 Dalio 宏观周期定位系统 V3")
st.caption("三周期叠加 + 29模板历史匹配 + 路径预测 | 新浪V5 + 东方财富 + World Bank")

# ═══ 刷新 ═══
if st.button("🔄 刷新诊断", type="primary"):
    with st.spinner("抓取数据 + 运行引擎..."):
        import subprocess
        subprocess.run(["bash", str(Path(__file__).parent.parent / "run_daily.sh")],
                       capture_output=True, timeout=90)
    st.rerun()

result = diagnose()
match_result = run_matcher()

# ═══ 三列：周期仪表 ═══
st.markdown("---")
st.subheader("📍 三周期定位")
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

# ═══ 压力测试 ═══
st.markdown("---")
st.subheader("⚠️ 反向压力测试")
from engine.stress_test import monitor as stress_monitor
stress = stress_monitor()
st.caption("极端场景前置条件监控 | 激活度>40% 需关注")

cols = st.columns(4)
sorted_stress = sorted(stress.values(), key=lambda x: x["activation_pct"], reverse=True)
for i, s in enumerate(sorted_stress[:12]):
    with cols[i % 4]:
        severity_icon = {"extreme": "💀", "severe": "🔴", "moderate": "🟡"}.get(s["severity"], "⚪")
        st.markdown(f"""
        <div style="background:#1e1e2e;border-left:4px solid {s['color']};border-radius:8px;padding:10px;margin-bottom:8px;">
            <strong>{severity_icon} {s['label']}</strong> [{s['severity']}]<br>
            <span style="color:{s['color']};font-size:1.2em">{s['activation_pct']}%</span> <small>{s['met_count']}/{s['total_count']} 条件</small><br>
            <small style="color:#888">{s['description'][:60]}...</small>
        </div>
        """, unsafe_allow_html=True)

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
st.caption(f"最后更新: {date.today()} | V3引擎 | 29模板 | Hermes + DeepSeek V4 Pro")
