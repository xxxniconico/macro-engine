"""Divergence Detector — 指标背离检测。

Dalio 核心理念：「最危险的时刻不是指标指向风险，
而是指标之间开始互相矛盾」——这正是转折点的前兆。

检测维度：
  1. VIX vs S&P 背离 — 股市涨但恐慌也在涨
  2. 黄金 vs 实际利率背离 — 金价涨但实际利率也在涨
  3. 曲线 vs PMI 背离 — 曲线倒挂但PMI还在扩张
  4. 美元 vs 新兴市场背离 — 美元跌但新兴市场没涨
  5. 叙事 vs 数据背离 — 媒体看多但硬数据走弱
"""

import sqlite3
from pathlib import Path
from datetime import date, timedelta

DB = Path("/home/xxxsuli/macro-engine/macro.db")

def get_recent(conn, indicator: str, days: int = 90):
    """Get values for last N days, return list of (date, value)."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT date, value FROM macro_indicators "
        "WHERE indicator_name=? AND date >= ? ORDER BY date",
        (indicator, cutoff)
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def trend(values: list) -> float:
    """Simple linear trend: 1.0 = rising, -1.0 = falling, 0.0 = flat."""
    if len(values) < 3:
        return 0.0
    n = len(values)
    # Slope of last N vs first N/2 average
    mid = n // 2
    first_avg = sum(v[1] for v in values[:mid]) / mid
    last_avg = sum(v[1] for v in values[-mid:]) / mid
    if first_avg == 0:
        return 0.0
    change = (last_avg - first_avg) / abs(first_avg)
    return max(-1.0, min(1.0, change * 5))  # 归一化到 [-1, 1]


def detect_all() -> dict:
    """Run all divergence checks."""
    conn = sqlite3.connect(str(DB))
    divergences = []
    today = date.today().isoformat()

    # ── 1. VIX vs S&P 背离 ──
    try:
        sp = get_recent(conn, "us_sp500", 90)
        vix = get_recent(conn, "us_vixy", 90)
        sp_trend = trend(sp)
        vix_trend = trend(vix)
        # Healthy: SP↑ + VIX↓ (negative correlation)
        # Divergence: SP↑ + VIX↑ (both rising = danger)
        if sp_trend > 0.3 and vix_trend > 0.3:
            divergences.append({
                "type": "🟡 VIX-S&P 背离",
                "severity": "warning",
                "detail": f"标普涨(sp={sp_trend:.2f})但VIX也在涨(vix={vix_trend:.2f}) → 市场在买保险，尾部对冲需求上升",
                "pair": ("us_sp500", "us_vixy"),
            })
        elif sp_trend < -0.3 and vix_trend < -0.3:
            divergences.append({
                "type": "🟢 VIX-S&P 正常",
                "severity": "normal",
                "detail": "标普跌+VIX跌 → 风险偏好回升，正常",
                "pair": ("us_sp500", "us_vixy"),
            })
    except:
        pass

    # ── 2. 黄金 vs 实际利率背离 ──
    try:
        gold = get_recent(conn, "gold", 90)
        real_rate = get_recent(conn, "us_real_rate", 90)
        gold_trend = trend(gold)
        rate_trend = trend(real_rate)
        # Healthy: Gold↓ + RealRate↑ (negative correlation)
        # Divergence: Gold↑ + RealRate↑ (both rising = structural shift)
        if gold_trend > 0.3 and rate_trend > 0.2:
            divergences.append({
                "type": "🔴 黄金-利率背离",
                "severity": "critical",
                "detail": f"金价涨(gold={gold_trend:.2f})+实际利率涨(rate={rate_trend:.2f}) → 传统负相关被打破，去美元化/地缘驱动金价",
                "pair": ("gold", "us_real_rate"),
            })
    except:
        pass

    # ── 3. 曲线 vs PMI 背离 ──
    try:
        curve = get_recent(conn, "us_yield_curve", 180)
        pmi = get_recent(conn, "us_pmi", 180)
        if curve and pmi:
            latest_curve = curve[-1][1]
            latest_pmi = pmi[-1][1]
            pmi_3m_ago = pmi[0][1] if len(pmi) > 2 else latest_pmi
            # Divergence: curve deeply inverted but PMI hasn't deteriorated yet
            if latest_curve < 0.88 and latest_pmi > 49 and pmi_3m_ago > latest_pmi:
                divergences.append({
                    "type": "⚠️ 曲线-PMI背离",
                    "severity": "warning",
                    "detail": f"曲线深度倒挂({latest_curve:.3f})但PMI仍>{49}({latest_pmi:.1f}) → PMI通常滞后曲线6-12月，衰退信号尚未被PMI确认",
                    "pair": ("us_yield_curve", "us_pmi"),
                })
    except:
        pass

    # ── 4. 美元 vs 新兴市场背离 ──
    try:
        dollar = get_recent(conn, "us_uup", 90)
        em = get_recent(conn, "em_eem", 90)
        dollar_trend = trend(dollar)
        em_trend = trend(em)
        # Healthy: Dollar↑ + EM↓ (negative correlation)
        # Divergence: Dollar↓ + EM↓ (EM not benefiting from weak dollar)
        if dollar_trend < -0.2 and em_trend < 0:
            divergences.append({
                "type": "🟡 美元-新兴背离",
                "severity": "warning",
                "detail": f"美元走弱(dxy={dollar_trend:.2f})但新兴市场未涨(em={em_trend:.2f}) → 全球风险偏好低下，资本不愿进入新兴市场",
                "pair": ("us_uup", "em_eem"),
            })
    except:
        pass

    # ── 5. 叙事 vs 硬数据背离 ──
    try:
        sentiment = conn.execute(
            "SELECT sentiment_score, bull_ratio, divergence_score FROM sentiment_history ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if sentiment:
            sent_score, bull_ratio, div_score = sentiment
            if bull_ratio > 0.7 and div_score > 15:
                divergences.append({
                    "type": "🚨 叙事-数据背离",
                    "severity": "critical",
                    "detail": f"媒体极度看多(牛熊比={bull_ratio:.0%})但硬数据背离度={div_score} → Dalio：所有人都在船上时，船最容易翻",
                    "pair": ("narrative", "hard_data"),
                })
            elif bull_ratio < 0.3 and div_score > 15:
                divergences.append({
                    "type": "🟢 过度悲观",
                    "severity": "info",
                    "detail": f"媒体极度看空(牛熊比={bull_ratio:.0%})但数据背离 → 可能是反向买入信号",
                    "pair": ("narrative", "hard_data"),
                })
    except:
        pass

    conn.close()

    # Summary
    n_critical = sum(1 for d in divergences if d["severity"] == "critical")
    n_warning = sum(1 for d in divergences if d["severity"] == "warning")

    return {
        "date": today,
        "divergences": divergences,
        "n_divergences": len(divergences),
        "n_critical": n_critical,
        "n_warning": n_warning,
        "summary": (
            f"🔴{n_critical}项严重背离 🟡{n_warning}项预警"
            if n_critical + n_warning > 0
            else "🟢 无显著背离"
        ),
    }


if __name__ == "__main__":
    result = detect_all()
    print(f"Divergence Detector — {result['date']}")
    print(f"  {result['summary']}")
    for d in result["divergences"]:
        print(f"  {d['type']}: {d['detail'][:100]}")
