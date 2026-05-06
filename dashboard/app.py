"""Streamlit 看板 V3 — Dalio 宏观周期定位系统 + 历史模板匹配。"""

import sys, sqlite3, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import date

from engine.cycle_locator import diagnose
from engine.template_matcher import run_matcher, FEATURE_NAMES
from data.storage import get_indicator_count, get_snapshot

st.set_page_config(
    page_title="Dalio 宏观周期定位",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dalio 宏观周期定位系统")
st.caption("基于 Ray Dalio 三周期叠加框架 | 数据源：东方财富 + 新浪财经 + World Bank")

# ═══ 刷新 ═══
col_refresh, col_info = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 刷新诊断", type="primary"):
        with st.spinner("抓取数据 + 运行引擎 + 模板匹配..."):
            import subprocess
            subprocess.run(["bash", str(Path(__file__).parent.parent / "run_daily.sh")],
                           capture_output=True, timeout=90)
        st.rerun()

result = diagnose()
snap = get_snapshot()
match_result = run_matcher()

# ═══ 三列：周期仪表 ═══
st.markdown("---")
st.subheader("📍 三周期定位")

col1, col2, col3 = st.columns(3)

with col1:
    short = result["short_term"]
    color = "🟢" if short["score"] > 0.2 else ("🟡" if short["score"] > -0.2 else "🔴")
    st.metric(
        f"短期债务周期",
        f"{color} {short['stage']}",
        f"置信度 {short['confidence']:.0%}"
    )
    if short.get("signals"):
        for k, v in short["signals"].items():
            st.caption(f"• {k}: {v}")

with col2:
    long = result["long_term"]
    color = "🟢" if long["score"] > 0.2 else ("🟡" if long["score"] > -0.2 else "🔴")
    st.metric(
        f"长期债务周期",
        f"{color} {long['stage']}",
        f"置信度 {long['confidence']:.0%}"
    )
    if long.get("signals"):
        for k, v in long["signals"].items():
            st.caption(f"• {k}: {v}")

with col3:
    empire = result["empire"]
    color = "🟢" if empire["score"] > 0 else ("🟡" if empire["score"] > -0.4 else "🔴")
    st.metric(
        f"帝国/秩序周期",
        f"{color} {empire['stage']}",
        f"置信度 {empire['confidence']:.0%}"
    )
    if empire.get("signals"):
        for k, v in empire["signals"].items():
            st.caption(f"• {k}: {v}")

# ═══ 风险条 ═══
st.markdown("---")
st.subheader("⚠️ 综合风险评估")
risk = result["risk"]
if "高" in risk: st.error(f"🔴 高风险 — 三周期中至少两个处于危险区间")
elif "中" in risk: st.warning(f"🟡 中等风险 — 一个周期处于危险区间")
else: st.success(f"🟢 低风险 — 所有周期处于正常区间")

# ═══ 历史模板匹配 ═══
st.markdown("---")
st.subheader("🔍 历史模板匹配")
st.caption(f"余弦相似度匹配 | 可用特征 {match_result['available_features']}/{match_result['total_features']}")

if match_result.get("message"):
    st.warning(match_result["message"])
elif match_result["matches"]:
    # Top 5 匹配卡片
    cols = st.columns(min(5, len(match_result["matches"])))
    for i, m in enumerate(match_result["matches"]):
        with cols[i]:
            sim_pct = m["similarity"] * 100
            color = "#1a8a1a" if sim_pct > 70 else ("#d4a800" if sim_pct > 40 else "#cc3333")
            st.markdown(f"""
            <div style="
                background: #1e1e2e;
                border-left: 4px solid {color};
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
                height: 100%;
            ">
                <strong>#{i+1}</strong> <span style="color:{color}">{m['similarity']*100:.1f}%</span><br>
                <small>{m['name']}</small><br>
                <small style="color:#888">{m['country']} | {m['period']}</small><br>
                <small style="color:#aaa">重叠 {m['overlap']} 维</small>
            </div>
            """, unsafe_allow_html=True)

    # 相似度柱状图
    st.markdown("#### 相似度分布")
    names = [m["name"] for m in match_result["matches"]]
    sims = [m["similarity"] * 100 for m in match_result["matches"]]
    colors = ["#1a8a1a" if s > 70 else ("#d4a800" if s > 40 else "#cc3333") for s in sims]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=sims, y=names, orientation='h',
        marker_color=colors,
        text=[f"{s:.1f}%" for s in sims],
        textposition='outside',
    ))
    fig_bar.update_layout(
        height=250,
        margin=dict(l=200, r=40, t=0, b=0),
        xaxis=dict(range=[0, max(sims)*1.3], title="相似度 %"),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # 历史结果详情
    with st.expander("📖 历史结果详情"):
        for i, m in enumerate(match_result["matches"]):
            st.markdown(f"**#{i+1} {m['name']}** ({m['similarity']*100:.1f}%)")
            st.caption(m["outcome"])
            st.markdown("---")

# ═══ 数据覆盖 ═══
st.markdown("---")
st.subheader("📦 数据覆盖")
st.text(f"数据库指标种类: {get_indicator_count()} | 最新快照: {len(snap)} 条 | 数据源: 新浪 + 东方财富 + World Bank")

# ═══ 图表 ═══
st.markdown("---")
st.subheader("📈 关键指标走势")

conn = sqlite3.connect(str(Path(__file__).parent.parent / "macro.db"))
df_cn = pd.read_sql("SELECT date, value FROM macro_indicators WHERE indicator_name='china_gdp_growth' ORDER BY date", conn)
df_us = pd.read_sql("SELECT date, value FROM macro_indicators WHERE indicator_name='us_gdp_growth' ORDER BY date", conn)
df_gold = pd.read_sql("SELECT date, value FROM macro_indicators WHERE indicator_name='gold' ORDER BY date", conn)
conn.close()

tab1, tab2, tab3 = st.tabs(["GDP 增速对比", "黄金走势", "原始数据"])

with tab1:
    if not df_cn.empty and not df_us.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_cn["date"], y=df_cn["value"], name="中国 GDP 增速", line=dict(color="red")))
        fig.add_trace(go.Scatter(x=df_us["date"], y=df_us["value"], name="美国 GDP 增速", line=dict(color="blue")))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=400, title="中美 GDP 增速对比 (1960-2024)", yaxis_title="%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("暂无 GDP 历史数据（运行 worldbank.py 获取）")

with tab2:
    if not df_gold.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_gold["date"], y=df_gold["value"], name="黄金(美元/盎司)", line=dict(color="gold")))
        fig.update_layout(height=400, title="黄金价格走势")
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.dataframe(pd.DataFrame([{"指标":k, "值":v["value"], "信心":v["confidence"], "日期":v["date"]}
                               for k,v in sorted(snap.items())]), use_container_width=True)

st.markdown("---")
st.caption(f"最后更新: {date.today()} | Hermes Agent + OpenCode | DeepSeek V4 Pro | 模板匹配引擎 V1")
