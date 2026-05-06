"""反向压力测试引擎 — Dalio 的"如果最坏情况发生"分析。

核心理念：从极端场景出发，回溯需要满足什么前置条件，
然后实时监控这些条件的激活度。

场景 → 前置条件 → 激活度监控 → 概率更新
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot


# ═══════════════════════════════════════════════════════
#  极端场景定义
# ═══════════════════════════════════════════════════════

SCENARIOS = {
    "us_debt_crisis": {
        "label": "美国债务危机",
        "severity": "extreme",
        "preconditions": [
            ("us_debt_gdp", ">", 130),
            ("usd_reserve_share", "<", 55),
            ("us_political_polarization", ">", 80),
            ("us_yield_curve", "<", 0.92),
        ],
        "assumed_impact": {
            "usd": "-30%（美元贬值）",
            "gold": "+50%（金价飙升）",
            "stocks": "-40%（美股暴跌）",
            "bonds": "US10Y +200bp（长端利率飙升）",
        },
        "description": "市场对美国国债信心崩溃 → 拍卖失败 → 美元储备地位急剧下降",
    },
    "china_hard_landing": {
        "label": "中国硬着陆",
        "severity": "severe",
        "preconditions": [
            ("china_debt_gdp", ">", 310),
            ("china_pmi", "<", 48),
            ("china_unemployment", ">", 6),
            ("china_cpi", "<", -0.5),
        ],
        "assumed_impact": {
            "CNY": "-15%（人民币贬值）",
            "commodities": "-30%（大宗暴跌）",
            "hong_kong": "-40%（港股重挫）",
            "global_gdp": "-1.5pp（拖累全球）",
        },
        "description": "房地产+地方政府债务螺旋 → 通缩 → 银行危机 → 经济硬着陆",
    },
    "global_stagflation": {
        "label": "全球滞胀",
        "severity": "severe",
        "preconditions": [
            ("us_cpi", ">", 4),
            ("china_cpi", ">", 3),
            ("us_unemployment", ">", 5),
            ("gold", ">", 5000),
        ],
        "assumed_impact": {
            "stocks": "-25%（全球股市）",
            "bonds": "滞胀 = 股债双杀",
            "commodities": "黄金$6000+，石油$150+",
        },
        "description": "供给冲击+货币宽松后遗症 → 通胀顽固+增长停滞 → 央行两难",
    },
    "reserve_currency_shift": {
        "label": "储备货币更替",
        "severity": "extreme",
        "preconditions": [
            ("usd_reserve_share", "<", 50),
            ("us_political_polarization", ">", 85),
            ("us_debt_gdp", ">", 140),
            ("gold", ">", 5500),
        ],
        "assumed_impact": {
            "order": "全球秩序重组",
            "usd": "-40-60%",
            "gold": "新的全球货币锚",
            "timeline": "5-15年过渡期",
        },
        "description": "美元储备份额跌破50% → 多极货币体系 → 类似1920s英镑到美元的过渡",
    },
    "japanification": {
        "label": "日本化（长期通缩停滞）",
        "severity": "moderate",
        "preconditions": [
            ("china_debt_gdp", ">", 300),
            ("china_cpi", "<", 0),
            ("china_population_growth", "<", -0.5),
            ("china_pmi", "<", 49),
        ],
        "assumed_impact": {
            "growth": "0-2% 长期低增长",
            "rates": "零利率常态化",
            "equity": "低回报+高波动",
        },
        "description": "人口下降+债务高企+通缩 → 日本式失去的三十年",
    },
    "ai_disruption_crisis": {
        "label": "AI 颠覆性失业危机",
        "severity": "moderate",
        "preconditions": [
            ("us_unemployment", ">", 6),
            ("technology_adoption_rate", ">", 80),
            ("income_inequality_gini", ">", 0.45),
        ],
        "assumed_impact": {
            "jobs": "白领大规模失业",
            "society": "UBI 讨论加速",
            "markets": "科技股先涨后跌",
        },
        "description": "AI 替代白领工作 → 结构性失业 → 社会契约重写",
    },

    # ═══ 新增场景 ═══

    "commercial_real_estate_crash": {
        "label": "商业地产崩盘",
        "severity": "severe",
        "preconditions": [
            ("us_yield_curve", "<", 0.92),
            ("us_unemployment", ">", 5),
            ("us_fed_rate", ">", 4),
            ("us_vixy", ">", 30),
        ],
        "assumed_impact": {
            "cre_prices": "-30-50%（办公楼估值）",
            "regional_banks": "中小银行倒闭潮",
            "stocks": "REITs -50%，金融股 -30%",
        },
        "description": "远程办公+高利率+再融资墙 → 商业地产估值暴跌 → 区域银行危机",
    },

    "china_shadow_banking_crisis": {
        "label": "中国影子银行危机",
        "severity": "severe",
        "preconditions": [
            ("china_debt_gdp", ">", 290),
            ("china_pmi", "<", 49),
            ("china_shadow_banking_npl", ">", 8),
            ("china_trust_defaults", ">", 3),
        ],
        "assumed_impact": {
            "wealth_products": "理财赎回潮",
            "local_banks": "城商行挤兑风险",
            "contagion": "港/A股联动暴跌",
        },
        "description": "信托违约 → 理财产品亏损 → 零售投资者恐慌 → 中小银行流动性危机",
    },

    "fed_policy_error": {
        "label": "美联储政策错误",
        "severity": "severe",
        "preconditions": [
            ("us_cpi", ">", 3),
            ("us_unemployment", ">", 4.5),
            ("us_yield_curve", "<", 0.90),
            ("us_vixy", ">", 25),
        ],
        "assumed_impact": {
            "recession": "2026 H2 衰退概率>60%",
            "fed": "被迫紧急降息+重启QE",
            "credibility": "Fed 信誉严重受损",
        },
        "description": "降息太晚/太慢 → 硬着陆 → 滞胀型衰退 → 央行信誉危机",
    },

    "us_china_financial_decoupling": {
        "label": "美中金融脱钩",
        "severity": "extreme",
        "preconditions": [
            ("usd_reserve_share", "<", 55),
            ("us_political_polarization", ">", 80),
            ("em_eem", "<", 55),
            ("us_uup", ">", 28),
        ],
        "assumed_impact": {
            "cn_stocks": "中概股退市 -40%",
            "trade": "全面金融制裁",
            "globalization": "两个平行金融体系",
        },
        "description": "金融制裁升级 → 资本账户冻结 → SWIFT 替代 → 全球金融体系分裂",
    },

    "taiwan_strait_crisis": {
        "label": "台海地缘危机",
        "severity": "extreme",
        "preconditions": [
            ("china_pmi", "<", 48),
            ("china_unemployment", ">", 6),
            ("us_political_polarization", ">", 85),
            ("geopolitical_tension_index", ">", 90),
        ],
        "assumed_impact": {
            "semiconductor": "全球芯片断供",
            "shipping": "太平洋航线瘫痪",
            "markets": "全球股市 -20-40%",
            "gold": "金价冲击$6000+",
        },
        "description": "台海军事升级 → 半导体断供 → 全球供应链崩溃 → 军事对抗",
    },

    "global_food_energy_crisis": {
        "label": "全球粮食能源危机",
        "severity": "severe",
        "preconditions": [
            ("us_cpi", ">", 5),
            ("us_uso", ">", 160),
            ("em_eem", "<", 55),
            ("geopolitical_conflict_count", ">", 5),
        ],
        "assumed_impact": {
            "food": "粮价翻倍，新兴市场饥荒",
            "energy": "油价$150+",
            "politics": "多国政府倒台",
        },
        "description": "气候灾害+地缘冲突+出口禁令 → 粮/能价格飙升 → 新兴市场社会动荡",
    },

    "us_constitutional_crisis": {
        "label": "美国宪政危机",
        "severity": "extreme",
        "preconditions": [
            ("us_political_polarization", ">", 85),
            ("us_wealth_gap", ">", 0.45),
            ("us_institutional_trust", "<", 30),
            ("us_social_unrest_index", ">", 70),
        ],
        "assumed_impact": {
            "governance": "政府功能瘫痪",
            "dollar": "美元信心崩塌",
            "civil_order": "大规模社会动荡",
        },
        "description": "政治极化临界点 → 制度失效 → 宪政危机 → Dalio 30-40%内战概率场景",
    },

    "brics_currency_challenge": {
        "label": "金砖货币挑战",
        "severity": "moderate",
        "preconditions": [
            ("usd_reserve_share", "<", 58),
            ("gold", ">", 4500),
            ("em_eem", ">", 65),
            ("brics_trade_share", ">", 40),
        ],
        "assumed_impact": {
            "dollar_demand": "全球储备需求结构性下降",
            "gold": "央行购金加速",
            "multipolar": "多极货币体系成形",
        },
        "description": "BRICS 贸易结算去美元化 → 央行购金潮 → 美元储备份额加速下降",
    },

    # ═══ 第三批 ═══

    "derivatives_crisis": {
        "label": "衍生品/掉期爆雷",
        "severity": "extreme",
        "preconditions": [
            ("us_yield_curve", "<", 0.88),
            ("us_vixy", ">", 30),
            ("us_fed_rate", ">", 4),
            ("us_sp500", ">", 7000),
        ],
        "assumed_impact": {
            "contagion": "类似 LTCM 1998 ×10",
            "counterparty": "大行违约连锁反应",
            "fed": "被迫大规模注入流动性",
        },
        "description": "高利率+高杠杆+波动率突升 → 掉期/衍生品保证金链断裂 → 系统性冲击",
    },

    "carbon_bubble": {
        "label": "碳泡沫破裂",
        "severity": "moderate",
        "preconditions": [
            ("us_uso", "<", 130),
            ("carbon_price", ">", 100),
            ("esg_flows", "<", -10),
            ("us_sp500", "<", 5000),
        ],
        "assumed_impact": {
            "energy_stocks": "化石能源股 -40-60%",
            "stranded_assets": "万亿美元搁浅资产",
            "transition": "能源转型加速 vs 石油国崩溃",
        },
        "description": "碳定价+ESG撤资 → 化石能源搁浅资产 → 石油出口国财政危机 → 地缘重组",
    },

    "china_capital_flight": {
        "label": "中国资本外逃",
        "severity": "severe",
        "preconditions": [
            ("china_debt_gdp", ">", 290),
            ("china_pmi", "<", 49),
            ("china_cpi", "<", 0),
            ("us_uup", ">", 28),
        ],
        "assumed_impact": {
            "cny": "人民币贬破 8.5",
            "hk": "港币联系汇率承压",
            "controls": "资本管制全面升级",
        },
        "description": "经济信心恶化 → 富人/企业转移资产 → 外汇储备骤降 → 资本管制 → 外资撤离加速",
    },

    "european_fragmentation": {
        "label": "欧洲碎片化危机",
        "severity": "severe",
        "preconditions": [
            ("eurozone_debt_gdp", ">", 100),
            ("eurozone_unemployment", ">", 9),
            ("eurozone_political_fragmentation", ">", 70),
            ("ecb_rate", ">", 3),
        ],
        "assumed_impact": {
            "italy": "意大利 BTP-Bund 利差 >400bp",
            "euro": "欧元跌至 0.85",
            "eu": "欧盟解体讨论再起",
        },
        "description": "高债务+高利率+民粹 → 南欧债务危机重演 → 欧元区生存危机",
    },

    "pension_crisis": {
        "label": "养老金偿付危机",
        "severity": "severe",
        "preconditions": [
            ("us_fed_rate", ">", 3),
            ("us_demographic_ratio", "<", 2.5),
            ("pension_funding_gap", ">", 30),
            ("us_yield_curve", "<", 0.90),
        ],
        "assumed_impact": {
            "public_pensions": "州/市养老金破产",
            "muni_bonds": "市政债暴跌",
            "social_contract": "退休年龄被迫推迟",
        },
        "description": "低利率+老龄化+给付刚性 → 养老金缺口暴露 → 政府被迫削减福利 → 社会契约危机",
    },

    "cyber_financial_warfare": {
        "label": "网络金融战",
        "severity": "extreme",
        "preconditions": [
            ("us_political_polarization", ">", 80),
            ("geopolitical_tension_index", ">", 75),
            ("us_vixy", ">", 25),
            ("cyber_incident_count", ">", 10),
        ],
        "assumed_impact": {
            "markets": "交易所被迫暂停",
            "banks": "支付系统瘫痪",
            "trust": "数字金融信心崩塌",
        },
        "description": "国家级网络攻击 → 金融基础设施瘫痪 → SWIFT/支付系统中断 → 现金回归 → 全球市场冻结",
    },

    # ═══ 战争场景 ═══

    "south_china_sea_conflict": {
        "label": "南海军事冲突",
        "severity": "extreme",
        "preconditions": [
            ("us_political_polarization", ">", 80),
            ("china_pmi", "<", 49),
            ("usd_reserve_share", "<", 55),
            ("naval_incident_count", ">", 5),
        ],
        "assumed_impact": {
            "shipping": "全球 30% 海运中断",
            "oil": "油价飙至 $200+",
            "semiconductor": "芯片供应链断裂",
            "insurance": "战争险费率暴涨 50 倍",
        },
        "description": "南海撞船/撞机 → 军事对峙升级 → 海上封锁 → 全球贸易断崖 → 能源/芯片危机",
    },

    "korean_peninsula_war": {
        "label": "朝鲜半岛战争",
        "severity": "extreme",
        "preconditions": [
            ("china_pmi", "<", 48),
            ("us_political_polarization", ">", 85),
            ("nk_provocation_index", ">", 90),
            ("us_forces_korea_alert", ">", 3),
        ],
        "assumed_impact": {
            "seoul": "首尔 24h 内遭受炮击",
            "semiconductor": "全球存储芯片断供 70%",
            "china": "中国被迫卷入",
            "markets": "亚太股市 -50%，全球 -30%",
        },
        "description": "朝鲜第七次核试验+ICBM → 美韩先发制人打击 → 首尔毁灭性炮击 → 中美被迫介入",
    },

    "middle_east_full_war": {
        "label": "中东全面战争",
        "severity": "extreme",
        "preconditions": [
            ("us_uso", ">", 150),
            ("us_vixy", ">", 30),
            ("strait_of_hormuz_threat", ">", 80),
            ("me_conflict_countries", ">", 4),
        ],
        "assumed_impact": {
            "oil": "油价 $250+ → 全球经济衰退",
            "horman": "霍尔木兹海峡封锁",
            "gold": "金价 $7000+",
            "refugees": "千万级难民潮冲击欧洲",
        },
        "description": "伊朗-以色列全面开战 → 霍尔木兹封锁 → 沙特油田遭袭 → 全球石油供应缺口 20%",
    },

    "russia_nato_direct": {
        "label": "俄-北约直接冲突",
        "severity": "extreme",
        "preconditions": [
            ("nato_article5_trigger", ">", 70),
            ("russia_mobilization_level", ">", 80),
            ("baltic_incident_count", ">", 3),
            ("us_troops_europe", ">", 150000),
        ],
        "assumed_impact": {
            "nuclear_risk": "核升级风险 30-50%",
            "europe": "欧洲大陆战争",
            "energy": "欧洲能源彻底断供",
            "markets": "全球市场熔断式暴跌",
        },
        "description": "波罗的海擦枪走火 → 北约第五条触发 → 常规战争 → 核升级临界点 → 1962 年以来最危险",
    },

    "india_pakistan_brink": {
        "label": "印巴核边缘",
        "severity": "extreme",
        "preconditions": [
            ("kashmir_incident_count", ">", 5),
            ("india_pakistan_troop_level", ">", 80),
            ("terror_attack_casualties", ">", 200),
            ("nuclear_rhetoric_level", ">", 85),
        ],
        "assumed_impact": {
            "nuclear": "战术核武器首次实战使用",
            "asia": "南亚核冬天风险",
            "global": "全球核禁忌打破",
            "markets": "全球市场恐慌性抛售",
        },
        "description": "克什米尔恐袭 → 印度越境打击 → 巴基斯坦战术核武 → 全球核禁忌被打破",
    },

    "energy_chokepoint_blockade": {
        "label": "能源航道封锁",
        "severity": "severe",
        "preconditions": [
            ("us_uso", ">", 140),
            ("us_vixy", ">", 25),
            ("naval_tension_index", ">", 70),
            ("insurance_war_risk", ">", 10),
        ],
        "assumed_impact": {
            "oil": "霍尔木兹/马六甲封锁 → 油价 $300+",
            "lng": "全球 LNG 断供",
            "economy": "全球 GDP 骤降 5-8%",
            "navy": "多国海军护航 → 擦枪走火风险",
        },
        "description": "地缘冲突升级 → 关键航道封锁 → 能源运输中断 → 全球工业停摆 → 军事护航 → 冲突扩大",
    },

    "global_war_alliance": {
        "label": "全球阵营化战争",
        "severity": "extreme",
        "preconditions": [
            ("usd_reserve_share", "<", 50),
            ("us_political_polarization", ">", 90),
            ("china_debt_gdp", ">", 310),
            ("active_conflict_theaters", ">", 3),
        ],
        "assumed_impact": {
            "ww3_risk": "第三次世界大战风险 20-30%",
            "economy": "全球经济分裂为两大阵营",
            "trade": "贸易额暴跌 60%",
            "gold": "金本位回归讨论",
        },
        "description": "多战区同时爆发 → 中美全面对抗 → 全球分裂为两大阵营 → 类似 1930s 格局 → 秩序重组",
    },
}


# ═══════════════════════════════════════════════════════

def _get_indicator(snap: dict, name: str) -> Optional[float]:
    """从快照获取指标，支持别名。"""
    aliases = {
        "us_debt_gdp": ["us_debt_gdp", "us_govt_debt_gdp"],
        "us_political_polarization": ["us_political_polarization"],
        "us_yield_curve": ["us_yield_curve"],
        "usd_reserve_share": ["usd_reserve_share"],
        "china_debt_gdp": ["china_debt_gdp"],
        "china_pmi": ["china_pmi"],
        "china_cpi": ["china_cpi"],
        "china_unemployment": ["china_unemployment"],
        "china_population_growth": ["china_population_growth"],
        "income_inequality_gini": ["us_wealth_gap"],
        "us_unemployment": ["us_unemployment"],
        "us_cpi": ["us_cpi"],
        "gold": ["gold"],
        "technology_adoption_rate": [],
        "us_fed_rate": ["us_fed_rate"],
        "us_vixy": ["us_vixy"],
        "us_uup": ["us_uup"],
        "em_eem": ["em_eem"],
        "us_uso": ["us_uso"],
        "china_shadow_banking_npl": [],
        "china_trust_defaults": [],
        "geopolitical_tension_index": [],
        "geopolitical_conflict_count": [],
        "us_institutional_trust": [],
        "us_social_unrest_index": [],
        "brics_trade_share": [],
        "carbon_price": [],
        "esg_flows": [],
        "eurozone_debt_gdp": [],
        "eurozone_unemployment": [],
        "eurozone_political_fragmentation": [],
        "ecb_rate": [],
        "us_demographic_ratio": [],
        "pension_funding_gap": [],
        "cyber_incident_count": [],
        "us_sp500": ["us_sp500"],
        "naval_incident_count": [],
        "nk_provocation_index": [],
        "us_forces_korea_alert": [],
        "strait_of_hormuz_threat": [],
        "me_conflict_countries": [],
        "nato_article5_trigger": [],
        "russia_mobilization_level": [],
        "baltic_incident_count": [],
        "us_troops_europe": [],
        "kashmir_incident_count": [],
        "india_pakistan_troop_level": [],
        "terror_attack_casualties": [],
        "nuclear_rhetoric_level": [],
        "naval_tension_index": [],
        "insurance_war_risk": [],
        "active_conflict_theaters": [],
    }

    for alias in aliases.get(name, [name]):
        entry = snap.get(alias, {})
        val = entry.get("value")
        if val is not None:
            return val
    return None


def _check_precondition(snap: dict, indicator: str, op: str, threshold: float) -> bool:
    val = _get_indicator(snap, indicator)
    if val is None:
        return None  # 数据不可用
    if op == ">":
        return val > threshold
    if op == "<":
        return val < threshold
    if op == ">=":
        return val >= threshold
    if op == "<=":
        return val <= threshold
    return False


def monitor() -> dict:
    """监控所有极端场景的前置条件激活度。

    Returns:
        {scenario_id: {label, severity, activation_pct, met_count, total_count,
                       status, assumed_impact, description, details: [...]}}
    """
    snap = get_snapshot()
    results = {}

    for scenario_id, scenario in SCENARIOS.items():
        met = 0
        total = len(scenario["preconditions"])
        unavailable = 0
        details = []

        for indicator, op, threshold in scenario["preconditions"]:
            val = _get_indicator(snap, indicator)
            if val is None:
                unavailable += 1
                details.append({"indicator": indicator, "condition": f"{indicator} {op} {threshold}",
                                "current": "N/A", "met": False, "available": False})
                continue

            condition_met = _check_precondition(snap, indicator, op, threshold)
            details.append({
                "indicator": indicator,
                "condition": f"{indicator} {op} {threshold}",
                "current": val,
                "met": condition_met,
                "available": True,
            })
            if condition_met:
                met += 1

        effective_total = total - unavailable
        if effective_total > 0:
            activation_pct = met / effective_total * 100
        else:
            activation_pct = 0

        if activation_pct >= 70:
            status = "🔴 高危"
            color = "red"
        elif activation_pct >= 40:
            status = "🟡 关注"
            color = "yellow"
        else:
            status = "🟢 低概率"
            color = "green"

        results[scenario_id] = {
            "label": scenario["label"],
            "severity": scenario["severity"],
            "activation_pct": round(activation_pct, 1),
            "met_count": met,
            "total_count": effective_total,
            "unavailable_count": unavailable,
            "status": status,
            "color": color,
            "description": scenario["description"],
            "assumed_impact": scenario["assumed_impact"],
            "details": details,
        }

    return results


def format_report(monitor_result: dict) -> str:
    """格式化压力测试监控报告。"""
    lines = [
        "═" * 55,
        "  Dalio 反向压力测试",
        "  极端场景前置条件监控",
        "═" * 55,
    ]

    sorted_scenarios = sorted(monitor_result.values(),
                              key=lambda x: x["activation_pct"], reverse=True)

    for s in sorted_scenarios:
        severity_icon = {"extreme": "💀", "severe": "🔴", "moderate": "🟡"}.get(s["severity"], "⚪")
        lines.append(f"\n  {severity_icon} {s['status']} {s['label']} [{s['severity']}]")
        unavail_info = f", {s['unavailable_count']}项数据缺失" if s['unavailable_count'] else ""
        lines.append(f"     激活度: {s['activation_pct']}% ({s['met_count']}/{s['total_count']} 条件满足{unavail_info})")
        lines.append(f"     描述: {s['description']}")

        # 详细条件
        for d in s["details"]:
            if d["available"]:
                icon = "✓" if d["met"] else "✗"
                lines.append(f"       {icon} {d['condition']} → 当前: {d['current']}")
            else:
                lines.append(f"       ? {d['condition']} → 数据缺失")

    return "\n".join(lines)


if __name__ == "__main__":
    result = monitor()
    print(format_report(result))
    print()

    # 主关注场景
    print("═══ 需要关注的场景 ═══")
    for sid, s in result.items():
        if s["activation_pct"] >= 40:
            print(f"  {s['status']} {s['label']}: {s['activation_pct']}% 激活")
