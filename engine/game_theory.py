"""多方博弈引擎 — Dalio 框架的博弈视角。

核心理念：宏观不是单一力量驱动，而是多方参与者在各自约束下博弈的均衡。
关键不是问"我认为会发生什么"，而是问"各方在各自约束下会怎么做？"

追踪维度：
1. 各参与方目标与约束
2. 各方当前可用工具/牌
3. 各方最近动作
4. 冲突/协作关系
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot


# ═══════════════════════════════════════════════════════
#  参与方定义
# ═══════════════════════════════════════════════════════

PLAYERS = {
    "fed": {
        "name": "美联储",
        "mandate": "稳通胀(2%) + 最大就业",
        "constraints": ["政治压力", "财政主导风险", "市场绑架"],
        "tools": ["联邦基金利率(4.33%)", "资产负债表", "预期管理", "紧急贷款便利"],
        "recent_moves": ["维持高利率", "鸽派发言增多"],
        "indicators": ["us_fed_rate", "us_cpi", "us_unemployment"],
        "bias": "中性偏鸽 ⬇",
    },
    "china_gov": {
        "name": "中国政府",
        "mandate": "5%增长 + 社会稳定 + 产业升级",
        "constraints": ["地方债务", "房地产下行", "人口下降", "外部围堵"],
        "tools": ["货币宽松(降准降息)", "财政刺激(特别国债)", "产业政策", "汇率管理"],
        "recent_moves": ["适度宽松", "一揽子化债", "以旧换新补贴"],
        "indicators": ["china_pmi", "china_cpi", "china_debt_gdp"],
        "bias": "全力稳增长 ⬆",
    },
    "markets": {
        "name": "全球市场",
        "mandate": "风险收益最大化",
        "constraints": ["流动性环境", "监管", "地缘风险"],
        "tools": ["资金流向", "杠杆使用", "价格发现"],
        "recent_moves": ["科技股狂热", "避险资产齐涨(反常)", "新兴市场分化"],
        "indicators": ["us_sp500", "us_vixy", "em_eem", "us_tlt"],
        "bias": "科技乐观 + 尾部对冲 ⚡",
    },
    "china_markets": {
        "name": "中国资本市场",
        "mandate": "融资功能 + 财富效应",
        "constraints": ["政策干预", "信心脆弱", "外资流出"],
        "tools": ["国家队救市", "IPO节奏", "监管松紧"],
        "recent_moves": ["震荡蓄力", "AI概念活跃", "成交缩量"],
        "indicators": ["china_pmi", "china_cpi"],
        "bias": "等待政策信号 ⏸",
    },
    "eu": {
        "name": "欧盟/ECB",
        "mandate": "通胀<2% + 增长 + 一体化",
        "constraints": ["南欧债务", "德国衰退", "民粹上升", "能源转型"],
        "tools": ["ECB利率", "复苏基金", "产业补贴", "碳边境税"],
        "recent_moves": ["降息提前", "加大国防支出", "对华去风险"],
        "indicators": [],
        "bias": "防衰退优先 ⬇",
    },
    "commodity_producers": {
        "name": "资源出口国集团",
        "mandate": "资源收入最大化 + 主权基金增值",
        "constraints": ["能源转型压力", "价格波动", "地缘站队"],
        "tools": ["OPEC+产量调节", "主权财富基金", "计价货币选择"],
        "recent_moves": ["去美元贸易结算", "央行购金", "维持减产"],
        "indicators": ["gold", "us_uso"],
        "bias": "去美元化 + 高价维权 ⬆",
    },
}


# ═══════════════════════════════════════════════════════
#  博弈关系矩阵
# ═══════════════════════════════════════════════════════

RELATIONS = {
    ("fed", "markets"): "👀 市场绑架Fed — 降息预期太强，Fed通胀信誉受损",
    ("fed", "china_gov"): "🌊 间接影响 — Fed高利率 → 人民币压力 → 中国降息空间受限",
    ("china_gov", "china_markets"): "🎮 政策市 — 政府既要做多又要防风险，市场在等信号",
    ("china_gov", "commodity_producers"): "🤝 资源合作 — 石油人民币 + 金砖扩容 + 矿产协议",
    ("markets", "commodity_producers"): "📈 正相关 — 再通胀交易 → 商品涨 + 价值股涨",
    ("fed", "eu"): "🔄 联动 — ECB降息早于Fed → 欧元走弱 → 美元走强 → Fed难降息",
    ("china_gov", "eu"): "⚡ 竞争+合作 — 新能源竞争 + 对华依赖降低",
    ("markets", "china_markets"): "🔀 脱钩 — 美股独立牛市 vs A股政策市，相关性下降",
}


# ═══════════════════════════════════════════════════════
#  分析函数
# ═══════════════════════════════════════════════════════

def analyze() -> list[dict]:
    """分析各参与方当前状态。"""
    snap = get_snapshot()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    results = []
    for pid, player in PLAYERS.items():
        # 读取该参与方的关键指标
        key_vals = {}
        for ind in player["indicators"]:
            if ind in indicators:
                key_vals[ind] = indicators[ind]

        # 判断紧张度
        tension = 0.0
        if pid == "fed":
            if indicators.get("us_cpi", 0) > 3:
                tension += 0.3
            if indicators.get("us_yield_curve", 1) < 0.90:
                tension += 0.3
        elif pid == "china_gov":
            if indicators.get("china_debt_gdp", 0) > 280:
                tension += 0.3
            if indicators.get("china_pmi", 100) < 50:
                tension += 0.2
        elif pid == "markets":
            if indicators.get("us_vixy", 0) > 25:
                tension += 0.3
            if indicators.get("us_yield_curve", 1) < 0.90:
                tension += 0.2
        elif pid == "china_markets":
            if indicators.get("china_cpi", 10) < 0:
                tension += 0.3

        status = "🔴 高压" if tension > 0.4 else ("🟡 承压" if tension > 0.1 else "🟢 正常")

        results.append({
            "player": player["name"],
            "mandate": player["mandate"],
            "status": status,
            "bias": player["bias"],
            "tools": player["tools"][:3],
            "recent": player["recent_moves"][-1],
            "key_data": key_vals,
        })

    return results


def get_relations() -> list[dict]:
    """获取博弈关系矩阵。"""
    return [{"a": a, "b": b, "relation": r}
            for (a, b), r in RELATIONS.items()]


def get_net_effects() -> list[str]:
    """分析多方的净效应（各方行为加总后的宏观方向）。"""
    effects = []

    # 从当前数据推断净效应
    snap = get_snapshot()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    # 流动性方向
    curve = indicators.get("us_yield_curve", 1)
    if curve < 0.90:
        effects.append("🔻 流动性：Fed高利率 + 曲线倒挂 → 全球流动性收紧 → 套利交易风险")
    else:
        effects.append("↔️ 流动性：中性偏紧")

    # 风险偏好
    vix = indicators.get("us_vixy", 20)
    sp500 = indicators.get("us_sp500", 5000)
    gold_yr = 0
    gold_now = indicators.get("gold", 0)
    gold_ref = indicators.get("gold_1y_reference")
    if gold_ref and gold_ref > 0:
        gold_yr = (gold_now - gold_ref) / gold_ref * 100

    if vix > 25 and gold_yr > 30:
        effects.append("🔴 风险偏好：分裂 — 股市追高 + 黄金暴涨 = 市场内部矛盾")
    elif vix < 20:
        effects.append("🟢 风险偏好：乐观一致")
    else:
        effects.append("🟡 风险偏好：谨慎乐观")

    # 去美元化方向
    reserve = indicators.get("usd_reserve_share", 60)
    if reserve < 55:
        effects.append("🔴 去美元化：加速 — 储备份额跌破55% + 金砖扩容")
    elif reserve < 58:
        effects.append("🟡 去美元化：进行中 — 储备份额低于58%")
    else:
        effects.append("🟢 去美元化：缓慢")

    # 中国政策方向
    pmi = indicators.get("china_pmi", 50)
    if pmi < 50:
        effects.append("🔻 中国：政策加码预期 — PMI < 50，更多刺激在路上")
    else:
        effects.append("↔️ 中国：温和复苏 — PMI > 50，政策以稳为主")

    # 地缘方向
    if vix > 25 and gold_yr > 40:
        effects.append("🔴 地缘：风险溢价上升 — VIX+黄金双高暗示市场定价冲突风险")
    else:
        effects.append("🟡 地缘：维持现状")

    return effects


def format_report(results: list[dict]) -> str:
    """格式化博弈分析报告。"""
    lines = [
        "═" * 55,
        "  Dalio 多方博弈分析",
        "  各参与方立场与约束",
        "═" * 55,
    ]

    for r in results:
        lines.append(f"\n  {r['status']} **{r['player']}**")
        lines.append(f"     目标: {r['mandate']}")
        lines.append(f"     倾向: {r['bias']}")
        if r["key_data"]:
            kv = ", ".join(f"{k}={v}" for k, v in r["key_data"].items())
            lines.append(f"     数据: {kv}")

    # 净效应
    lines.append(f"\n  ═══ 多方博弈净效应 ═══")
    for effect in get_net_effects():
        lines.append(f"  {effect}")

    # 关键关系
    lines.append(f"\n  ═══ 关键博弈关系 ═══")
    for r in get_relations():
        lines.append(f"  {r['relation']}")

    return "\n".join(lines)


if __name__ == "__main__":
    result = analyze()
    print(format_report(result))
