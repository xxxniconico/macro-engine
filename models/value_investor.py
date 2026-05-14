"""
巴菲特 B-Score 量化筛选引擎

将巴菲特的四层框架转化为可计算的 0-100 评分系统：
  第一层: 企业质量 (40分) — ROE/ROIC/FCF/毛利
  第二层: 护城河   (25分) — 份额/定价/ROIC持续/增长
  第三层: 财务健康 (15分) — 杠杆/流动/利息覆盖
  第四层: 安全边际 (20分) — 所有者盈余/P-E/P-B/PEG

用法:
  python models/value_investor.py --ticker 600519       # A股
  python models/value_investor.py --ticker AAPL          # 美股
  python models/value_investor.py --json '{"name":"XX", ...}'  # 手动输入
"""

from dataclasses import dataclass, field
from typing import Optional
import json, sys, math


@dataclass
class FinancialData:
    """一只股票的财务数据 — 用户提供或通过 API 获取。"""
    name: str = ""
    ticker: str = ""
    sector: str = ""

    # 近年财务数据 (按年，最近在前)
    years: list[int] = field(default_factory=list)
    revenue: list[float] = field(default_factory=list)       # 营业收入(亿)
    net_income: list[float] = field(default_factory=list)    # 净利润(亿)
    equity: list[float] = field(default_factory=list)        # 股东权益(亿)
    total_assets: list[float] = field(default_factory=list)  # 总资产(亿)
    total_debt: list[float] = field(default_factory=list)    # 有息负债(亿)
    current_assets: list[float] = field(default_factory=list)
    current_liab: list[float] = field(default_factory=list)
    ocf: list[float] = field(default_factory=list)           # 经营活动现金流
    capex: list[float] = field(default_factory=list)         # 资本支出
    ebit: list[float] = field(default_factory=list)
    interest_expense: list[float] = field(default_factory=list)
    gross_margin: list[float] = field(default_factory=list)  # 毛利率%
    shares_outstanding: list[float] = field(default_factory=list)  # 总股本(亿)

    # 当前市场数据
    price: float = 0.0
    market_cap: float = 0.0  # 亿
    pe_5y_avg: float = 0.0   # 5年PE均值

    # 行业参考
    sector_roe_median: float = 0.0
    sector_gm_median: float = 0.0

    @property
    def n_years(self) -> int:
        return len(self.years)

    def latest(self, arr: list[float], idx: int = 0) -> float:
        """安全取数组第 idx 个元素。"""
        return arr[idx] if idx < len(arr) else 0.0

    def avg(self, arr: list[float], n: int = 5) -> float:
        """取前 n 年均值。"""
        a = arr[:n]
        return sum(a) / len(a) if a else 0.0

    def stdev(self, arr: list[float], n: int = 5) -> float:
        """取前 n 年标准差。"""
        a = arr[:n]
        if len(a) < 2:
            return 0.0
        m = sum(a) / len(a)
        return math.sqrt(sum((x - m) ** 2 for x in a) / (len(a) - 1))


# ═══════════════════════════════════════════════════════
#  B-Score 核心计算
# ═══════════════════════════════════════════════════════

def calc_roe(d: FinancialData) -> list[float]:
    """ROE = 净利润 / 股东权益。"""
    return [d.net_income[i] / d.equity[i] * 100 if d.equity[i] > 0 else 0
            for i in range(min(len(d.net_income), len(d.equity)))]

def calc_roic(d: FinancialData) -> list[float]:
    """ROIC ≈ EBIT×(1-税率) / (股东权益+有息负债-超额现金)。简化：EBIT/投入资本。"""
    roic = []
    for i in range(min(len(d.ebit), len(d.equity), len(d.total_debt))):
        capital = d.equity[i] + d.total_debt[i]
        roic.append(d.ebit[i] / capital * 100 if capital > 0 else 0)
    return roic

def calc_owner_earnings(d: FinancialData, idx: int = 0) -> float:
    """所有者盈余 ≈ OCF - 维持性Capex (Capex × 0.7)。"""
    oc = d.latest(d.ocf, idx)
    cx = d.latest(d.capex, idx)
    return oc - cx * 0.7

def calc_pe(d: FinancialData) -> float:
    """当前 P/E。"""
    ni = d.latest(d.net_income)
    if ni <= 0:
        return 999
    return d.market_cap / ni if d.market_cap > 0 else 999

def calc_peg(d: FinancialData) -> float:
    """PEG = P/E ÷ 3年净利润CAGR。"""
    pe = calc_pe(d)
    ni = d.net_income[:4]
    if len(ni) >= 2 and ni[0] > 0 and ni[-1] > 0:
        cagr = (ni[0] / ni[-1]) ** (1 / (len(ni) - 1)) - 1
        return pe / (cagr * 100) if cagr > 0 else 999
    return 999


def score_quality(d: FinancialData) -> dict:
    """第一层：企业质量 (40分)。"""
    roe = calc_roe(d)
    roic = calc_roic(d)
    oe = calc_owner_earnings(d)
    ni = d.latest(d.net_income)

    # ROE 趋势 (20)
    roe_last5 = roe[:5]
    roe_avg = sum(roe_last5) / len(roe_last5) if roe_last5 else 0
    roe_min = min(roe_last5) if roe_last5 else 0
    roe_trend_up = len(roe_last5) >= 2 and all(roe_last5[i] >= roe_last5[i+1] for i in range(len(roe_last5)-1))

    if roe_avg > 20 and roe_trend_up:
        roe_score, roe_detail = 20, f"ROE均{roe_avg:.0f}% 5年持续上升"
    elif roe_avg > 15 and roe_min >= 12:
        roe_score, roe_detail = 16, f"ROE均{roe_avg:.0f}% 稳定高位"
    elif roe_avg > 12 and roe_min >= 10:
        roe_score, roe_detail = 12, f"ROE均{roe_avg:.0f}% 有小波动"
    elif roe_avg > 10:
        roe_score, roe_detail = 8, f"ROE均{roe_avg:.0f}% 一般"
    elif roe_last5 and roe_last5[0] >= 10:
        roe_score, roe_detail = 4, f"ROE最近{roe_last5[0]:.0f}% 低于10%"
    else:
        roe_score, roe_detail = 0, "ROE过低或为负"

    # ROIC vs WACC (10) — 简化WACC≈8%
    roic_last3 = roic[:3]
    roic_avg = sum(roic_last3) / len(roic_last3) if roic_last3 else 0
    spread = roic_avg - 8  # 简化WACC=8%
    if spread > 10 and all(r > 18 for r in roic[:3] if len(roic) >= 3):
        roic_score, roic_detail = 10, f"ROIC-WACC={spread:.0f}% 大幅超额"
    elif spread > 5 and all(r > 13 for r in roic[:3] if len(roic) >= 3):
        roic_score, roic_detail = 8, f"ROIC-WACC={spread:.0f}% 明显超额"
    elif spread > 0:
        roic_score, roic_detail = 6, f"ROIC-WACC={spread:.0f}% 有超额"
    elif spread > -5:
        roic_score, roic_detail = 3, f"ROIC-WACC={spread:.0f}% 接近WACC"
    else:
        roic_score, roic_detail = 0, f"ROIC-WACC={spread:.0f}% 低于WACC"

    # FCF 质量 (5)
    if ni > 0:
        fcf_ratio = oe / ni
    else:
        fcf_ratio = 0
    if fcf_ratio > 1.0:
        fcf_score, fcf_detail = 5, f"FCF/NI={fcf_ratio:.1f} 优异"
    elif fcf_ratio > 0.8:
        fcf_score, fcf_detail = 4, f"FCF/NI={fcf_ratio:.1f} 良好"
    elif fcf_ratio > 0.5:
        fcf_score, fcf_detail = 3, f"FCF/NI={fcf_ratio:.1f} 一般"
    elif fcf_ratio > 0:
        fcf_score, fcf_detail = 2, f"FCF/NI={fcf_ratio:.1f} 偏弱"
    else:
        fcf_score, fcf_detail = 0, "FCF为负"

    # 毛利稳定性 (5)
    gm = d.gross_margin[:5]
    if gm:
        gm_avg = sum(gm) / len(gm)
        gm_cv = d.stdev(d.gross_margin, 5) / gm_avg * 100 if gm_avg > 0 else 999
        if gm_cv < 5:
            gm_score, gm_detail = 5, f"毛利率{gm_avg:.0f}% CV={gm_cv:.1f}% 极稳"
        elif gm_cv < 10:
            gm_score, gm_detail = 4, f"毛利率{gm_avg:.0f}% CV={gm_cv:.1f}% 稳定"
        elif gm_cv < 20:
            gm_score, gm_detail = 2, f"毛利率{gm_avg:.0f}% CV={gm_cv:.1f}% 波动"
        else:
            gm_score, gm_detail = 0, f"毛利率CV={gm_cv:.0f}% 不稳"
    else:
        gm_score, gm_detail = 0, "无毛利数据"

    total = roe_score + roic_score + fcf_score + gm_score
    return {"score": total, "max": 40, "detail": [roe_detail, roic_detail, fcf_detail, gm_detail],
            "subscores": {"roe": roe_score, "roic": roic_score, "fcf": fcf_score, "gm": gm_score}}


def score_moat(d: FinancialData) -> dict:
    """第二层：护城河 (25分)。简化为 ROIC持久 + 毛利趋势 + 收入增长。"""
    roic = calc_roic(d)
    gm = d.gross_margin[:5]
    rev = d.revenue[:5]

    # ROIC 持久性 (10)
    roic5 = roic[:5]
    if roic5:
        roic_avg = sum(roic5) / len(roic5)
        roic_min = min(roic5)
        if roic_avg > 15 and roic_min > 12:
            persist_score, persist_detail = 10, f"ROIC均{roic_avg:.0f}% 最低{roic_min:.0f}% 极持久"
        elif roic_avg > 12 and roic_min > 8:
            persist_score, persist_detail = 8, f"ROIC均{roic_avg:.0f}% 最低{roic_min:.0f}% 持久"
        elif roic_avg > 10:
            persist_score, persist_detail = 6, f"ROIC均{roic_avg:.0f}% 较稳"
        elif roic_avg > 5:
            persist_score, persist_detail = 3, f"ROIC均{roic_avg:.0f}% 一般"
        else:
            persist_score, persist_detail = 0, "ROIC过低"
    else:
        persist_score, persist_detail = 0, "无数据"

    # 定价能力 = 毛利趋势 (8)
    if len(gm) >= 3:
        gm_trend = all(gm[i] >= gm[i+1] for i in range(len(gm)-1))
        gm_avg = sum(gm) / len(gm)
        if gm_trend and gm[-1] > gm[0] * 1.05:
            gm_score, gm_detail = 8, f"毛利率{len(gm)}年持续上升 {gm[0]:.0f}%→{gm[-1]:.0f}%"
        elif gm_avg > 30 and d.stdev(d.gross_margin, len(gm)) / gm_avg < 0.1:
            gm_score, gm_detail = 6, f"毛利率{gm_avg:.0f}% 高位稳定"
        elif abs(gm[0] - gm_avg) / gm_avg < 0.1 if gm_avg > 0 else False:
            gm_score, gm_detail = 4, f"毛利率{gm_avg:.0f}% 持平"
        elif gm[0] > gm[-1] * 0.85:
            gm_score, gm_detail = 2, f"毛利率{gm_avg:.0f}% 轻微下降"
        else:
            gm_score, gm_detail = 0, f"毛利率持续下降"
    else:
        gm_score, gm_detail = 0, "数据不足"

    # 收入增长 (7)
    if len(rev) >= 2:
        cagr = (rev[0] / rev[-1]) ** (1 / (len(rev) - 1)) - 1 if rev[-1] > 0 else 0
        neg_years = sum(1 for i in range(len(rev)-1) if rev[i] < rev[i+1])
        if cagr > 0.10 and neg_years == 0:
            rev_score, rev_detail = 7, f"收入CAGR={cagr*100:.0f}% 无负增长"
        elif cagr > 0.08 and neg_years <= 1:
            rev_score, rev_detail = 5, f"收入CAGR={cagr*100:.0f}% 稳健"
        elif cagr > 0.05:
            rev_score, rev_detail = 3, f"收入CAGR={cagr*100:.0f}%"
        elif cagr > 0:
            rev_score, rev_detail = 1, f"收入微增 {cagr*100:.0f}%"
        else:
            rev_score, rev_detail = 0, "收入下滑"
    else:
        rev_score, rev_detail = 0, "数据不足"

    total = persist_score + gm_score + rev_score
    return {"score": total, "max": 25, "detail": [persist_detail, gm_detail, rev_detail],
            "subscores": {"persist": persist_score, "pricing": gm_score, "growth": rev_score}}


def score_health(d: FinancialData) -> dict:
    """第三层：财务健康 (15分)。"""
    de = d.latest(d.total_debt) / d.latest(d.equity) if d.latest(d.equity) > 0 else 999
    cr = d.latest(d.current_assets) / d.latest(d.current_liab) if d.latest(d.current_liab) > 0 else 0
    ic = d.latest(d.ebit) / d.latest(d.interest_expense) if d.latest(d.interest_expense) > 0 else 999

    # 债务 (8)
    if de < 0.3:
        debt_score, debt_detail = 8, f"D/E={de:.2f} 极低杠杆"
    elif de < 0.5:
        debt_score, debt_detail = 6, f"D/E={de:.2f} 低杠杆"
    elif de < 1.0:
        debt_score, debt_detail = 4, f"D/E={de:.2f} 适中"
    elif de < 2.0:
        debt_score, debt_detail = 2, f"D/E={de:.2f} 偏高"
    else:
        debt_score, debt_detail = 0, f"D/E={de:.2f} 高杠杆⚠️"

    # 流动 (4)
    if cr > 2.0:
        liq_score, liq_detail = 4, f"流动比率={cr:.1f} 充裕"
    elif cr > 1.5:
        liq_score, liq_detail = 3, f"流动比率={cr:.1f} 良好"
    elif cr > 1.0:
        liq_score, liq_detail = 2, f"流动比率={cr:.1f} 一般"
    else:
        liq_score, liq_detail = 0, f"流动比率={cr:.1f} 不足⚠️"

    # 利息覆盖 (3)
    if ic > 10:
        cover_score, cover_detail = 3, f"利息覆盖={ic:.0f}x 极安全"
    elif ic > 5:
        cover_score, cover_detail = 2, f"利息覆盖={ic:.0f}x 安全"
    elif ic > 2:
        cover_score, cover_detail = 1, f"利息覆盖={ic:.0f}x 偏低"
    else:
        cover_score, cover_detail = 0, f"利息覆盖={ic:.0f}x 危险⚠️"

    total = debt_score + liq_score + cover_score
    return {"score": total, "max": 15, "detail": [debt_detail, liq_detail, cover_detail],
            "subscores": {"debt": debt_score, "liquidity": liq_score, "coverage": cover_score}}


def score_margin(d: FinancialData) -> dict:
    """第四层：安全边际 (20分)。"""
    oe = calc_owner_earnings(d)
    oe_yield = oe / d.market_cap * 100 if d.market_cap > 0 else 0
    pe = calc_pe(d)
    pb = d.price / (d.latest(d.equity) / d.latest(d.shares_outstanding)) if d.latest(d.shares_outstanding) > 0 and d.latest(d.equity) > 0 else 0
    peg = calc_peg(d)
    roe_latest = d.latest(calc_roe(d))

    # 所有者盈余收益率 (10)
    if oe_yield > 10:
        oe_score, oe_detail = 10, f"OE收益率={oe_yield:.1f}% 极佳"
    elif oe_yield > 7:
        oe_score, oe_detail = 8, f"OE收益率={oe_yield:.1f}% 优秀"
    elif oe_yield > 5:
        oe_score, oe_detail = 6, f"OE收益率={oe_yield:.1f}% 良好"
    elif oe_yield > 3:
        oe_score, oe_detail = 4, f"OE收益率={oe_yield:.1f}% 一般"
    else:
        oe_score, oe_detail = 2, f"OE收益率={oe_yield:.1f}% 偏低"

    # P/E 历史对比 (5) - 无历史PE时用绝对值
    if d.pe_5y_avg > 0:
        pe_ratio = pe / d.pe_5y_avg
        if pe_ratio < 0.7:
            pe_score, pe_detail = 5, f"PE={pe:.0f} vs 5年均{d.pe_5y_avg:.0f} 低估"
        elif pe_ratio < 0.85:
            pe_score, pe_detail = 4, f"PE={pe:.0f} vs 5年均{d.pe_5y_avg:.0f} 偏低"
        elif pe_ratio < 1.15:
            pe_score, pe_detail = 3, f"PE={pe:.0f} vs 5年均{d.pe_5y_avg:.0f} 合理"
        elif pe_ratio < 1.5:
            pe_score, pe_detail = 1, f"PE={pe:.0f} vs 5年均{d.pe_5y_avg:.0f} 偏高"
        else:
            pe_score, pe_detail = 0, f"PE={pe:.0f} vs 5年均{d.pe_5y_avg:.0f} 高估"
    else:
        # 绝对值判断
        if pe < 10:
            pe_score, pe_detail = 5, f"PE={pe:.0f} 绝对低估"
        elif pe < 15:
            pe_score, pe_detail = 4, f"PE={pe:.0f} 偏低"
        elif pe < 20:
            pe_score, pe_detail = 3, f"PE={pe:.0f} 合理"
        elif pe < 30:
            pe_score, pe_detail = 2, f"PE={pe:.0f} 偏高"
        else:
            pe_score, pe_detail = 0, f"PE={pe:.0f} 高估"

    # P/B 锚定 (3)
    if pb < 3 and roe_latest > 15:
        pb_score, pb_detail = 3, f"PB={pb:.1f} ROE={roe_latest:.0f}% 优质低估"
    elif pb < 5 and roe_latest > 12:
        pb_score, pb_detail = 2, f"PB={pb:.1f} ROE={roe_latest:.0f}% 合理"
    elif pb < 10:
        pb_score, pb_detail = 1, f"PB={pb:.1f} 偏贵"
    else:
        pb_score, pb_detail = 0, f"PB={pb:.1f} 可能泡沫"

    # PEG (2)
    if peg < 1.0:
        peg_score, peg_detail = 2, f"PEG={peg:.1f} 低估增长"
    elif peg < 1.5:
        peg_score, peg_detail = 1, f"PEG={peg:.1f} 合理"
    else:
        peg_score, peg_detail = 0, f"PEG={peg:.1f} 偏贵" if peg < 5 else "PEG无效"

    total = oe_score + pe_score + pb_score + peg_score
    return {"score": total, "max": 20, "detail": [oe_detail, pe_detail, pb_detail, peg_detail],
            "subscores": {"oe_yield": oe_score, "pe": pe_score, "pb": pb_score, "peg": peg_score}}


def check_red_flags(d: FinancialData) -> list[str]:
    """一票否决检查。"""
    flags = []
    roe = calc_roe(d)
    if roe and sum(roe[:5]) / min(5, len(roe)) < 10:
        flags.append(f"ROE 5年均值 {sum(roe[:5])/len(roe[:5]):.1f}% < 10%")
    
    oe = calc_owner_earnings(d)
    if oe < 0:
        flags.append(f"所有者盈余为负 ({oe:.1f}亿)")
    
    de = d.latest(d.total_debt) / d.latest(d.equity) if d.latest(d.equity) > 0 else 999
    if de > 3.0:
        flags.append(f"D/E={de:.1f} > 3.0 杠杆过高")
    
    gm = d.gross_margin[:5]
    if len(gm) >= 3 and gm[0] < gm[-1] * 0.7:
        flags.append(f"毛利率5年下降超30%: {gm[-1]:.0f}%→{gm[0]:.0f}%")
    
    return flags


def calculate_bscore(d: FinancialData) -> dict:
    """计算完整的 B-Score。"""
    red_flags = check_red_flags(d)

    quality = score_quality(d)
    moat = score_moat(d)
    health = score_health(d)
    margin = score_margin(d)

    total = quality["score"] + moat["score"] + health["score"] + margin["score"]

    # 评级
    if total >= 80:
        grade, stars = "巴菲特级别", "⭐⭐⭐⭐⭐"
    elif total >= 70:
        grade, stars = "优秀企业", "⭐⭐⭐⭐"
    elif total >= 60:
        grade, stars = "良好企业", "⭐⭐⭐"
    elif total >= 50:
        grade, stars = "一般企业", "⭐⭐"
    elif total >= 40:
        grade, stars = "有缺陷", "⭐"
    else:
        grade, stars = "不合格", "❌"

    return {
        "name": d.name,
        "ticker": d.ticker,
        "b_score": total,
        "grade": grade,
        "stars": stars,
        "red_flags": red_flags,
        "layers": {
            "quality": quality,
            "moat": moat,
            "health": health,
            "margin": margin,
        },
        "metrics": {
            "pe": round(calc_pe(d), 1),
            "pb": round(d.price / (d.latest(d.equity) / d.latest(d.shares_outstanding)) if d.latest(d.shares_outstanding) > 0 and d.latest(d.equity) > 0 else 0, 2),
            "roe": round(d.latest(calc_roe(d)), 1),
            "roe_5y_avg": round(sum(calc_roe(d)[:5]) / min(5, len(calc_roe(d))), 1) if calc_roe(d) else 0,
            "de": round(d.latest(d.total_debt) / d.latest(d.equity) if d.latest(d.equity) > 0 else 0, 2),
            "oe_yield": round(calc_owner_earnings(d) / d.market_cap * 100 if d.market_cap > 0 else 0, 2),
            "market_cap": round(d.market_cap, 0),
        }
    }


def format_report(result: dict) -> str:
    """格式化输出报告。"""
    m = result["metrics"]
    layers = result["layers"]
    flags = result["red_flags"]

    report = f"""
╔══════════════════════════════════════════════╗
║  巴菲特 B-Score 量化评估                      ║
╠══════════════════════════════════════════════╣
║  {result['name']} ({result['ticker']})
║  总分: {result['b_score']}/100  {result['stars']}  {result['grade']}
╚══════════════════════════════════════════════╝

📊 核心指标
━━━━━━━━━━━━━━━━━━━━━━━━━━
  PE: {m['pe']}   PB: {m['pb']}   ROE: {m['roe']}%
  5年均ROE: {m['roe_5y_avg']}%   D/E: {m['de']}
  OE收益率: {m['oe_yield']}%   市值: {m['market_cap']}亿

📋 四层评分
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    for lid, lname in [("quality", "企业质量"), ("moat", "护城河"), ("health", "财务健康"), ("margin", "安全边际")]:
        L = layers[lid]
        bar = "█" * int(L["score"] / L["max"] * 20) + "░" * (20 - int(L["score"] / L["max"] * 20))
        report += f"\n  [{lname}] {L['score']}/{L['max']} {bar}"
        for d in L["detail"]:
            report += f"\n    · {d}"

    if flags:
        report += f"\n\n🚨 红灯警告 ({len(flags)}项)\n" + "\n".join(f"  ✗ {f}" for f in flags)
    else:
        report += "\n\n✅ 无一票否决项"

    return report


# ═══════════════════════════════════════════════════════
#  示例数据
# ═══════════════════════════════════════════════════════

def demo_apple():
    """Apple (AAPL) — 示例。"""
    return FinancialData(
        name="Apple Inc", ticker="AAPL", sector="科技",
        years=[2024, 2023, 2022, 2021, 2020],
        # 财务数据单位：亿人民币 (近似)
        revenue=[28075, 27480, 28330, 26166, 20615],
        net_income=[7406, 7004, 7168, 6950, 4315],
        equity=[4531, 4863, 3804, 5042, 4922],
        total_assets=[25578, 26404, 25589, 26481, 23566],
        total_debt=[7375, 7749, 8071, 8016, 7557],
        current_assets=[10751, 11007, 9789, 9971, 10058],
        current_liab=[13584, 11368, 11456, 12066, 9513],
        ocf=[9255, 8104, 8888, 7497, 5092],
        capex=[723, 772, 740, 705, 405],
        ebit=[9161, 8387, 8721, 7633, 4568],
        interest_expense=[0, 0, 0, 0, 0],  # Apple 利息支出极低
        gross_margin=[46.2, 44.1, 43.3, 41.8, 38.2],
        shares_outstanding=[151.2, 157.6, 162.2, 167.0, 171.2],
        price=212.0, market_cap=32000, pe_5y_avg=28,
        sector_roe_median=25, sector_gm_median=40,
    )


def demo_kweichow_moutai():
    """贵州茅台 (600519) — 示例。"""
    return FinancialData(
        name="贵州茅台", ticker="600519", sector="白酒",
        years=[2024, 2023, 2022, 2021, 2020],
        revenue=[1743, 1506, 1276, 1095, 980],
        net_income=[862, 747, 627, 525, 467],
        equity=[2596, 2150, 1972, 1895, 1613],
        total_assets=[3123, 2727, 2546, 2552, 2134],
        total_debt=[0, 0, 0, 0, 0],  # 茅台无有息负债
        current_assets=[2187, 1843, 1766, 1783, 1524],
        current_liab=[500, 521, 494, 582, 457],
        ocf=[942, 666, 509, 640, 516],
        capex=[45, 50, 39, 35, 28],
        ebit=[1120, 960, 795, 675, 598],
        interest_expense=[0, 0, 0, 0, 0],
        gross_margin=[92.0, 92.0, 92.0, 91.6, 91.4],
        shares_outstanding=[12.56, 12.56, 12.56, 12.56, 12.56],
        price=1620, market_cap=20345, pe_5y_avg=35,
        sector_roe_median=20, sector_gm_median=70,
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="巴菲特 B-Score 量化筛选")
    parser.add_argument("--demo", choices=["aapl", "moutai", "all"], default="moutai",
                        help="运行示例")
    parser.add_argument("--json", type=str, help="JSON 格式财务数据")
    args = parser.parse_args()

    if args.json:
        d = json.loads(args.json)
        fd = FinancialData(**d)
        result = calculate_bscore(fd)
        print(format_report(result))
    elif args.demo == "aapl":
        result = calculate_bscore(demo_apple())
        print(format_report(result))
    elif args.demo == "moutai":
        result = calculate_bscore(demo_kweichow_moutai())
        print(format_report(result))
    else:
        for name, fn in [("Apple", demo_apple), ("茅台", demo_kweichow_moutai)]:
            result = calculate_bscore(fn())
            print(format_report(result))
            print("\n" + "=" * 50 + "\n")
