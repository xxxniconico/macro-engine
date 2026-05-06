"""周期定位引擎 V3 — 全指标接入版。

新增指标:
  短期: unemployment, fed_rate, VIXY, yield_curve
  长期: UUP(美元), credit_spread
  帝国: military/gini/education (手动种子)
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, save_diagnosis, get_indicator_count


# ═══════════════════════════════════════════════════════
#  短期债务周期 (5-8年)
#  权重: PMI 35% | CPI 20% | 失业 15% | 风险偏好 15% | 利率曲线 15%
# ═══════════════════════════════════════════════════════

def locate_short_term(snapshot: dict) -> dict:
    score = 0.0
    tw = 0.0
    sig = {}

    pmi = snapshot.get("china_pmi", {}).get("value")
    cpi = snapshot.get("china_cpi", {}).get("value")
    unemp = snapshot.get("china_unemployment", {}).get("value")
    sp500 = snapshot.get("us_sp500", {}).get("value")
    gold = snapshot.get("gold", {}).get("value")
    vixy = snapshot.get("us_vixy", {}).get("value")
    curve = snapshot.get("us_yield_curve", {}).get("value")

    # PMI — 权重最高 (35%)
    if pmi is not None:
        w = 0.35; tw += w
        if pmi > 52:       score += w * 1.0;  sig["pmi"] = f"强扩张({pmi})"
        elif pmi > 50:     score += w * 0.5;  sig["pmi"] = f"弱扩张({pmi})"
        elif pmi > 48:     score += w * -0.3; sig["pmi"] = f"弱收缩({pmi})"
        else:              score += w * -1.0; sig["pmi"] = f"强收缩({pmi})"

    # CPI (20%)
    if cpi is not None:
        w = 0.20; tw += w
        if cpi > 3:        score += w * -0.8; sig["cpi"] = f"高通胀({cpi}%)"
        elif cpi > 1.5:    score += w * 0.0;  sig["cpi"] = f"温和({cpi}%)"
        elif cpi < 0:      score += w * -0.5; sig["cpi"] = f"通缩({cpi}%)"
        else:              score += w * 0.3;  sig["cpi"] = f"低通胀({cpi}%)"

    # 失业率 (15%)
    if unemp is not None:
        w = 0.15; tw += w
        if unemp < 4:      score += w * 0.6;  sig["jobs"] = f"极紧({unemp}%)"
        elif unemp < 5.5:  score += w * 0.2;  sig["jobs"] = f"健康({unemp}%)"
        elif unemp < 7:    score += w * -0.3; sig["jobs"] = f"疲软({unemp}%)"
        else:              score += w * -0.8; sig["jobs"] = f"危机({unemp}%)"

    # 全球风险偏好 — SP500/黄金 + VIX (15%)
    risk_w = 0.0
    if sp500 and gold and gold > 0:
        w = 0.08; risk_w += w; tw += w
        ratio = sp500 / gold
        if ratio > 2.0:    score += w * 0.6;  sig["risk"] = f"高偏好({ratio:.1f})"
        elif ratio > 1.5:  score += w * 0.2;  sig["risk"] = f"中性({ratio:.1f})"
        else:              score += w * -0.5; sig["risk"] = f"避险({ratio:.1f})"

    if vixy is not None:
        w = 0.07; risk_w += w; tw += w
        if vixy < 15:      score += w * 0.5;  sig["fear"] = "平静"
        elif vixy < 25:    score += w * 0.0;  sig["fear"] = "正常"
        elif vixy < 35:    score += w * -0.5; sig["fear"] = "恐慌"
        else:              score += w * -1.0; sig["fear"] = "极度恐慌"

    # 利率曲线 (15%) — 倒挂 = 衰退信号
    if curve is not None:
        w = 0.15; tw += w
        if curve > 0.98:       score += w * 0.3;  sig["curve"] = "陡峭(扩张)"
        elif curve > 0.95:     score += w * 0.0;  sig["curve"] = "正常"
        elif curve > 0.90:     score += w * -0.4; sig["curve"] = "平坦(警告)"
        else:                  score += w * -0.8; sig["curve"] = f"倒挂(衰退)({curve:.3f})"

    if tw == 0:
        return {"stage": "数据不足", "confidence": 0, "score": 0, "signals": {}, "data_quality": "0%"}

    ns = score / tw
    if ns > 0.5:       stage = "扩张中期";   conf = 0.5 + abs(ns)*0.3
    elif ns > 0.15:    stage = "扩张初期";   conf = 0.5 + abs(ns)*0.3
    elif ns > -0.15:   stage = "扩张末期/筑底"; conf = 0.6
    elif ns > -0.5:    stage = "收缩初期";   conf = 0.5 + abs(ns)*0.3
    else:              stage = "收缩中期";   conf = min(0.85, 0.5 + abs(ns)*0.3)

    return {"stage": stage, "confidence": round(conf, 2), "score": round(ns, 2),
            "signals": sig, "data_quality": f"{tw:.0%}"}


# ═══════════════════════════════════════════════════════
#  长期债务周期 (50-75年)
#  权重: 债务/GDP 40% | 实际利率 20% | 黄金年涨幅 20% | 美元强弱 20%
# ═══════════════════════════════════════════════════════

def locate_long_term(snapshot: dict) -> dict:
    score = 0.0; tw = 0.0; sig = {}

    debt = snapshot.get("china_debt_gdp", {}).get("value")
    real_rate = snapshot.get("us_real_rate", {}).get("value")
    gold = snapshot.get("gold", {}).get("value")
    gold_1y = snapshot.get("gold_1y_reference", {}).get("value")
    uup = snapshot.get("us_uup", {}).get("value")

    # 债务/GDP (40%)
    if debt is not None:
        w = 0.40; tw += w
        if debt > 300:    score += w * -1.0; sig["debt"] = f"极高({debt:.0f}%)"
        elif debt > 250:  score += w * -0.5; sig["debt"] = f"高({debt:.0f}%)"
        elif debt < 150:  score += w * 0.5;  sig["debt"] = f"低({debt:.0f}%)"
        else:             score += w * 0.0;  sig["debt"] = f"中等({debt:.0f}%)"

    # 实际利率 (20%)
    if real_rate is not None:
        w = 0.20; tw += w
        if real_rate < -2:    score += w * -0.5; sig["real"] = f"深度负({real_rate:.1f}%)"
        elif real_rate < 0:   score += w * -0.2; sig["real"] = f"负({real_rate:.1f}%)"
        elif real_rate > 3:   score += w * -0.3; sig["real"] = f"高({real_rate:.1f}%)"
        else:                 score += w * 0.3;  sig["real"] = f"适中({real_rate:.1f}%)"

    # 黄金年涨幅 → 货币信心代理 (20%)
    if gold and gold_1y and gold_1y > 0:
        w = 0.20; tw += w
        change = (gold - gold_1y) / gold_1y * 100
        if change > 30:    score += w * -0.7; sig["gold_yr"] = f"暴涨({change:.0f}%)"
        elif change > 15:  score += w * -0.4; sig["gold_yr"] = f"涨({change:.0f}%)"
        elif change < -10: score += w * 0.3;  sig["gold_yr"] = f"跌({change:.0f}%)"
        else:              score += w * 0.0;  sig["gold_yr"] = f"稳({change:.0f}%)"

    # 美元强弱 — UUP ETF >28 = 强美元, <26 = 弱 (20%)
    if uup is not None:
        w = 0.20; tw += w
        if uup > 28:       score += w * -0.3; sig["dollar"] = f"强({uup})"
        elif uup > 26:     score += w * 0.0;  sig["dollar"] = f"中性({uup})"
        else:              score += w * 0.3;  sig["dollar"] = f"弱({uup})"

    if tw == 0:
        return {"stage": "数据不足", "confidence": 0, "score": 0, "signals": {}, "data_quality": "0%"}

    ns = score / tw
    if ns > 0.3:        stage = "再杠杆化"
    elif ns > -0.3:     stage = "去杠杆前"
    elif ns > -0.6:     stage = "去杠杆中-漂亮"
    else:               stage = "去杠杆中-丑陋"

    return {"stage": stage, "confidence": round(min(0.80, 0.4 + abs(ns)*0.3), 2),
            "score": round(ns, 2), "signals": sig, "data_quality": f"{tw:.0%}"}


# ═══════════════════════════════════════════════════════
#  帝国/秩序周期 (~250年)
# ═══════════════════════════════════════════════════════

def locate_empire(snapshot: dict) -> dict:
    score = 0.0; tw = 0.0; sig = {}

    rs = snapshot.get("usd_reserve_share", {}).get("value")
    pol = snapshot.get("us_political_polarization", {}).get("value")
    gap = snapshot.get("us_wealth_gap", {}).get("value")

    if rs is not None:
        w = 0.35; tw += w
        if rs < 50:        score += w * -1.0; sig["reserve"] = f"<50%({rs:.0f})"
        elif rs < 58:      score += w * -0.5; sig["reserve"] = f"↓({rs:.0f}%)"
        elif rs > 65:      score += w * 0.5;  sig["reserve"] = f"稳固({rs:.0f}%)"
        else:              score += w * 0;    sig["reserve"] = f"正常({rs:.0f}%)"

    if pol is not None:
        w = 0.25; tw += w
        if pol > 80:       score += w * -1.0; sig["polar"] = f"极度({pol})"
        elif pol > 60:     score += w * -0.5; sig["polar"] = f"高({pol})"
        else:              score += w * 0;    sig["polar"] = f"正常({pol})"

    if gap is not None:
        w = 0.25; tw += w
        if gap > 0.45:     score += w * -0.8; sig["gap"] = f"极高({gap})"
        elif gap > 0.40:   score += w * -0.4; sig["gap"] = f"高({gap})"
        else:              score += w * 0.2;  sig["gap"] = f"正常({gap})"

    # 新兴市场 ETF 作为全球去美元化代理 (15%)
    eem = snapshot.get("em_eem", {}).get("value")
    if eem is not None:
        w = 0.15; tw += w
        # EEM > 70 = 新兴市场强劲 → 去美元化加速
        if eem > 70:       score += w * -0.3; sig["em"] = f"强劲({eem})"
        elif eem > 55:     score += w * 0.0;  sig["em"] = f"正常({eem})"
        else:              score += w * 0.2;  sig["em"] = f"疲弱({eem})"

    if tw == 0:
        return {"stage": "数据不足", "confidence": 0, "score": 0, "signals": {}, "data_quality": "0%"}

    ns = score / tw
    if ns > 0.5:        stage = "和平繁荣(阶段3)"
    elif ns > 0:        stage = "过度自信(阶段4)"
    elif ns > -0.4:     stage = "泡沫恶化(阶段5)"
    elif ns > -0.7:     stage = "内部冲突(阶段6)"
    else:               stage = "革命风险(阶段7)"

    return {"stage": stage, "confidence": round(min(0.80, 0.3 + abs(ns)*0.3), 2),
            "score": round(ns, 2), "signals": sig, "data_quality": f"{tw:.0%}"}


# ═══════════════════════════════════════════════════════

def diagnose(date_str=None):
    snap = get_snapshot(date_str)
    short = locate_short_term(snap)
    long = locate_long_term(snap)
    empire = locate_empire(snap)

    risks = sum(1 for c in [short, long, empire] if c["score"] < -0.3)
    risk = "🔴 高风险" if risks >= 2 else ("🟡 中等" if risks == 1 else "🟢 低风险")

    summary = (
        f"【短期】{short['stage']} ({short['confidence']:.0%})\n"
        f"【长期】{long['stage']} ({long['confidence']:.0%})\n"
        f"【帝国】{empire['stage']} ({empire['confidence']:.0%})\n"
        f"【风险】{risk}\n"
        f"【数据】{get_indicator_count()}种指标 | "
        f"短期:{short['data_quality']} 长期:{long['data_quality']} 帝国:{empire['data_quality']}"
    )

    result = {"date": date_str or date.today().isoformat(),
              "short_term": short, "long_term": long, "empire": empire,
              "risk": risk, "summary": summary, "indicators": len(snap)}

    save_diagnosis(short["stage"], short["confidence"],
                   long["stage"], long["confidence"],
                   empire["stage"], empire["confidence"], result)
    return result


if __name__ == "__main__":
    r = diagnose()
    print("═" * 50)
    print("  Dalio 三周期诊断 V3")
    print("═" * 50)
    print(r["summary"])
    for name, cyc in [("短期", r["short_term"]), ("长期", r["long_term"]), ("帝国", r["empire"])]:
        if cyc.get("signals"):
            print(f"  [{name}] {cyc['signals']}")
