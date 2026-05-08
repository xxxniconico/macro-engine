"""因果链条引擎 — Dalio 框架的传导推演。

核心理念：宏观事件不是孤立的，而是多米诺骨牌。
每个节点 = 一个经济/政治/社会状态，
边 = 状态之间的因果传导（带滞后时间 + 触发条件）。

输入：当前已触发的节点
输出：未来 6/12/24 个月可能发生的事件链
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot


# ═══════════════════════════════════════════════════════
#  因果图定义 — 50+ 节点，按领域分组
#  格式: { node_id: { triggers: [...], consequences: [...], lag_months: {...} } }
# ═══════════════════════════════════════════════════════

CAUSAL_GRAPH = {
    # ── 利率/货币 ──
    "fed_hike": {
        "triggers": ["us_cpi > 3.5", "us_unemployment < 4"],
        "consequences": [
            "usd_strong", "em_capital_outflow", "housing_slowdown",
            "credit_tightening", "stock_pressure"
        ],
        "lag_months": {"usd_strong": 0, "em_capital_outflow": 2, "housing_slowdown": 3,
                       "credit_tightening": 1, "stock_pressure": 1},
        "label": "美联储加息"
    },
    "fed_cut": {
        "triggers": ["us_unemployment > 5.5", "us_cpi < 2"],
        "consequences": ["usd_weak", "em_capital_inflow", "credit_easing",
                         "stock_boost", "housing_recovery"],
        "lag_months": {"usd_weak": 1, "em_capital_inflow": 3, "credit_easing": 2,
                       "stock_boost": 1, "housing_recovery": 6},
        "label": "美联储降息"
    },
    "yield_curve_inversion": {
        "triggers": ["us_yield_curve < 0.95"],
        "consequences": ["recession_signal", "bank_margin_pressure", "credit_tightening"],
        "lag_months": {"recession_signal": 0, "bank_margin_pressure": 3, "credit_tightening": 2},
        "label": "收益率曲线倒挂"
    },
    "usd_strong": {
        "triggers": [],
        "consequences": ["em_debt_pressure", "commodity_weak", "us_export_slowdown"],
        "lag_months": {"em_debt_pressure": 3, "commodity_weak": 1, "us_export_slowdown": 6},
        "label": "美元走强"
    },
    "usd_weak": {
        "triggers": [],
        "consequences": ["gold_rally", "inflation_imported", "em_relief"],
        "lag_months": {"gold_rally": 1, "inflation_imported": 6, "em_relief": 3},
        "label": "美元走弱"
    },

    # ── 信贷/银行 ──
    "credit_tightening": {
        "triggers": ["fed_hike", "yield_curve_inversion"],
        "consequences": ["corporate_default_rise", "consumer_spending_slow", "small_bank_stress"],
        "lag_months": {"corporate_default_rise": 6, "consumer_spending_slow": 3, "small_bank_stress": 4},
        "label": "信贷紧缩"
    },
    "credit_easing": {
        "triggers": ["fed_cut"],
        "consequences": ["corporate_borrowing_boom", "m_and_a_surge", "consumer_credit_growth"],
        "lag_months": {"corporate_borrowing_boom": 2, "m_and_a_surge": 4, "consumer_credit_growth": 3},
        "label": "信贷宽松"
    },
    "bank_margin_pressure": {
        "triggers": ["yield_curve_inversion"],
        "consequences": ["small_bank_stress", "lending_standards_tighten"],
        "lag_months": {"small_bank_stress": 6, "lending_standards_tighten": 2},
        "label": "银行息差受压"
    },
    "small_bank_stress": {
        "triggers": ["credit_tightening", "bank_margin_pressure"],
        "consequences": ["bank_failure_risk", "deposit_flight", "credit_freeze"],
        "lag_months": {"bank_failure_risk": 3, "deposit_flight": 2, "credit_freeze": 4},
        "label": "中小银行承压"
    },
    "bank_failure_risk": {
        "triggers": ["small_bank_stress"],
        "consequences": ["panic_contagion", "fed_emergency", "market_crash_risk"],
        "lag_months": {"panic_contagion": 1, "fed_emergency": 0, "market_crash_risk": 2},
        "label": "银行倒闭风险"
    },

    # ── 房地产 ──
    "housing_slowdown": {
        "triggers": ["fed_hike", "mortgage_rate > 7"],
        "consequences": ["construction_job_loss", "consumer_confidence_drop", "home_price_decline"],
        "lag_months": {"construction_job_loss": 3, "consumer_confidence_drop": 2, "home_price_decline": 6},
        "label": "房市降温"
    },
    "housing_recovery": {
        "triggers": ["fed_cut", "mortgage_rate < 5"],
        "consequences": ["construction_boom", "consumer_confidence_rise", "wealth_effect_positive"],
        "lag_months": {"construction_boom": 6, "consumer_confidence_rise": 3, "wealth_effect_positive": 4},
        "label": "房市复苏"
    },
    "home_price_decline": {
        "triggers": ["housing_slowdown"],
        "consequences": ["negative_equity", "consumer_spending_slow", "mortgage_default_rise"],
        "lag_months": {"negative_equity": 2, "consumer_spending_slow": 4, "mortgage_default_rise": 6},
        "label": "房价下跌"
    },

    # ── 劳动力市场 ──
    "construction_job_loss": {
        "triggers": ["housing_slowdown"],
        "consequences": ["unemployment_rise", "regional_recession"],
        "lag_months": {"unemployment_rise": 3, "regional_recession": 6},
        "label": "建筑就业流失"
    },
    "unemployment_rise": {
        "triggers": ["construction_job_loss", "corporate_default_rise"],
        "consequences": ["consumer_spending_slow", "mortgage_default_rise", "political_discontent"],
        "lag_months": {"consumer_spending_slow": 2, "mortgage_default_rise": 6, "political_discontent": 12},
        "label": "失业率上升"
    },
    "recession_signal": {
        "triggers": ["yield_curve_inversion"],
        "consequences": ["corporate_hiring_freeze", "investment_decline"],
        "lag_months": {"corporate_hiring_freeze": 3, "investment_decline": 6},
        "label": "衰退信号"
    },

    # ── 企业/市场 ──
    "stock_pressure": {
        "triggers": ["fed_hike", "credit_tightening"],
        "consequences": ["wealth_effect_negative", "ipo_market_freeze", "venture_capital_pullback"],
        "lag_months": {"wealth_effect_negative": 1, "ipo_market_freeze": 3, "venture_capital_pullback": 6},
        "label": "股市承压"
    },
    "stock_boost": {
        "triggers": ["fed_cut", "credit_easing"],
        "consequences": ["wealth_effect_positive", "ipo_market_boom"],
        "lag_months": {"wealth_effect_positive": 1, "ipo_market_boom": 3},
        "label": "股市上涨"
    },
    "corporate_default_rise": {
        "triggers": ["credit_tightening", "consumer_spending_slow"],
        "consequences": ["unemployment_rise", "bank_loss_provision"],
        "lag_months": {"unemployment_rise": 3, "bank_loss_provision": 1},
        "label": "企业违约上升"
    },
    "market_crash_risk": {
        "triggers": ["bank_failure_risk", "panic_contagion"],
        "consequences": ["fed_emergency", "circuit_breaker_trigger", "global_contagion"],
        "lag_months": {"fed_emergency": 0, "circuit_breaker_trigger": 0, "global_contagion": 2},
        "label": "市场崩盘风险"
    },

    # ── 消费 ──
    "consumer_spending_slow": {
        "triggers": ["credit_tightening", "unemployment_rise", "consumer_confidence_drop", "home_price_decline"],
        "consequences": ["retail_sales_decline", "corporate_default_rise", "gdp_slowdown"],
        "lag_months": {"retail_sales_decline": 1, "corporate_default_rise": 6, "gdp_slowdown": 3},
        "label": "消费放缓"
    },
    "consumer_confidence_drop": {
        "triggers": ["housing_slowdown", "stock_pressure", "political_discontent"],
        "consequences": ["consumer_spending_slow", "saving_rate_rise"],
        "lag_months": {"consumer_spending_slow": 2, "saving_rate_rise": 1},
        "label": "消费信心下降"
    },
    "inflation_imported": {
        "triggers": ["usd_weak", "commodity_rally"],
        "consequences": ["consumer_pain", "fed_hike_pressure"],
        "lag_months": {"consumer_pain": 3, "fed_hike_pressure": 4},
        "label": "输入型通胀"
    },

    # ── 国际/地缘 ──
    "em_capital_outflow": {
        "triggers": ["fed_hike", "usd_strong"],
        "consequences": ["em_currency_crisis", "em_debt_pressure"],
        "lag_months": {"em_currency_crisis": 3, "em_debt_pressure": 2},
        "label": "新兴市场资本外流"
    },
    "em_currency_crisis": {
        "triggers": ["em_capital_outflow"],
        "consequences": ["em_inflation_spike", "em_political_crisis", "global_contagion"],
        "lag_months": {"em_inflation_spike": 2, "em_political_crisis": 6, "global_contagion": 3},
        "label": "新兴市场货币危机"
    },
    "global_contagion": {
        "triggers": ["em_currency_crisis", "market_crash_risk"],
        "consequences": ["safe_haven_rush", "global_recession_risk"],
        "lag_months": {"safe_haven_rush": 2, "global_recession_risk": 6},
        "label": "全球传染"
    },
    "commodity_weak": {
        "triggers": ["usd_strong", "global_recession_risk"],
        "consequences": ["commodity_exporters_stress"],
        "lag_months": {"commodity_exporters_stress": 6},
        "label": "商品价格走弱"
    },
    "commodity_rally": {
        "triggers": ["usd_weak", "geopolitical_conflict"],
        "consequences": ["inflation_imported", "commodity_exporters_boom"],
        "lag_months": {"inflation_imported": 3, "commodity_exporters_boom": 2},
        "label": "商品价格飙升"
    },
    "oil_shock": {
        "triggers": ["oil_wti > 110"],
        "consequences": ["inflation_imported", "consumer_pain", "fed_hike"],
        "lag_months": {"inflation_imported": 1, "consumer_pain": 3, "fed_hike": 2},
        "label": "油价冲击"
    },
    "oil_collapse": {
        "triggers": ["oil_wti < 40"],
        "consequences": ["commodity_exporters_stress", "energy_sector_default_risk", "global_recession_risk"],
        "lag_months": {"commodity_exporters_stress": 2, "energy_sector_default_risk": 6, "global_recession_risk": 12},
        "label": "油价暴跌"
    },

    # ── 政治/社会 ──
    "political_discontent": {
        "triggers": ["unemployment_rise", "consumer_pain", "wealth_gap_alert"],
        "consequences": ["populist_rise", "policy_uncertainty", "social_unrest_risk"],
        "lag_months": {"populist_rise": 12, "policy_uncertainty": 6, "social_unrest_risk": 18},
        "label": "政治不满"
    },
    "populist_rise": {
        "triggers": ["political_discontent"],
        "consequences": ["central_bank_independence_threat", "trade_war_escalation", "fiscal_profligacy"],
        "lag_months": {"central_bank_independence_threat": 12, "trade_war_escalation": 6, "fiscal_profligacy": 8},
        "label": "民粹崛起"
    },
    "central_bank_independence_threat": {
        "triggers": ["populist_rise", "fiscal_profligacy"],
        "consequences": ["inflation_expectations_unhinged", "currency_devaluation", "bond_market_revolt"],
        "lag_months": {"inflation_expectations_unhinged": 6, "currency_devaluation": 4, "bond_market_revolt": 8},
        "label": "央行独立性受威胁"
    },
    "trade_war_escalation": {
        "triggers": ["populist_rise"],
        "consequences": ["supply_chain_disruption", "inflation_imported", "global_gdp_drag"],
        "lag_months": {"supply_chain_disruption": 3, "inflation_imported": 6, "global_gdp_drag": 12},
        "label": "贸易战升级"
    },

    # ── 终极场景 ──
    "bond_market_revolt": {
        "triggers": ["central_bank_independence_threat", "fiscal_profligacy"],
        "consequences": ["sovereign_debt_crisis", "currency_collapse"],
        "lag_months": {"sovereign_debt_crisis": 6, "currency_collapse": 8},
        "label": "债券市场反抗"
    },
    "sovereign_debt_crisis": {
        "triggers": ["bond_market_revolt"],
        "consequences": ["austerity_forced", "imf_intervention", "reserve_status_questioned"],
        "lag_months": {"austerity_forced": 3, "imf_intervention": 6, "reserve_status_questioned": 12},
        "label": "主权债务危机"
    },
    "reserve_status_questioned": {
        "triggers": ["sovereign_debt_crisis", "currency_collapse"],
        "consequences": ["global_order_reshuffle", "new_reserve_currency_race"],
        "lag_months": {"global_order_reshuffle": 24, "new_reserve_currency_race": 18},
        "label": "储备地位动摇"
    },

    # ── 黄金/货币信心（新增）──
    "gold_surge_signal": {
        "triggers": ["gold > 4500"],
        "consequences": ["currency_confidence_erosion", "inflation_fear", "de_dollarization_talk"],
        "lag_months": {"currency_confidence_erosion": 3, "inflation_fear": 2, "de_dollarization_talk": 4},
        "label": "金价极端信号"
    },
    "inflation_fear": {
        "triggers": ["gold_surge_signal"],
        "consequences": ["safe_haven_rush", "fed_hike_pressure"],
        "lag_months": {"safe_haven_rush": 2, "fed_hike_pressure": 4},
        "label": "通胀恐惧升温"
    },
    "currency_confidence_erosion": {
        "triggers": ["gold_surge_signal"],
        "consequences": ["usd_reserve_decline", "alternative_reserve_search"],
        "lag_months": {"usd_reserve_decline": 6, "alternative_reserve_search": 8},
        "label": "货币信心动摇"
    },
    "de_dollarization_talk": {
        "triggers": ["gold_surge_signal"],
        "consequences": ["alternative_reserve_search", "brics_currency_push"],
        "lag_months": {"alternative_reserve_search": 6, "brics_currency_push": 12},
        "label": "去美元化讨论"
    },
    "cny_depreciation": {
        "triggers": ["usd_cny > 7.3"],
        "consequences": ["china_capital_outflow", "pboc_intervention", "em_currency_contagion"],
        "lag_months": {"china_capital_outflow": 2, "pboc_intervention": 0, "em_currency_contagion": 4},
        "label": "人民币急贬"
    },
    "china_capital_outflow": {
        "triggers": ["cny_depreciation"],
        "consequences": ["china_stock_pressure", "china_bond_selloff", "fx_reserve_decline"],
        "lag_months": {"china_stock_pressure": 1, "china_bond_selloff": 2, "fx_reserve_decline": 3},
        "label": "中国资本外流"
    },

    # ── 中国债务（新增）──
    "china_debt_stress": {
        "triggers": ["china_debt_gdp > 280"],
        "consequences": ["local_govt_stress", "bank_npl_concern"],
        "lag_months": {"local_govt_stress": 6, "bank_npl_concern": 9},
        "label": "中国债务高压"
    },
    "local_govt_stress": {
        "triggers": ["china_debt_stress"],
        "consequences": ["infra_spending_cut", "regional_bank_stress"],
        "lag_months": {"infra_spending_cut": 6, "regional_bank_stress": 12},
        "label": "地方政府承压"
    },
    "regional_bank_stress": {
        "triggers": ["local_govt_stress"],
        "consequences": ["credit_tightening", "deposit_flight", "local_credit_crunch"],
        "lag_months": {"credit_tightening": 3, "deposit_flight": 2, "local_credit_crunch": 1},
        "label": "区域性银行承压"
    },
    "bank_npl_concern": {
        "triggers": ["china_debt_stress"],
        "consequences": ["credit_tightening", "local_credit_crunch", "bank_loss_provision"],
        "lag_months": {"credit_tightening": 6, "local_credit_crunch": 3, "bank_loss_provision": 2},
        "label": "银行坏账忧虑"
    },
    "infra_spending_cut": {
        "triggers": ["local_govt_stress"],
        "consequences": ["construction_job_loss", "regional_recession_china"],
        "lag_months": {"construction_job_loss": 3, "regional_recession_china": 9},
        "label": "基建支出削减"
    },
    "local_credit_crunch": {
        "triggers": ["regional_bank_stress", "bank_npl_concern"],
        "consequences": ["corporate_default_rise", "consumer_spending_slow"],
        "lag_months": {"corporate_default_rise": 6, "consumer_spending_slow": 4},
        "label": "地方信贷紧缩"
    },
    "regional_recession_china": {
        "triggers": ["infra_spending_cut"],
        "consequences": ["unemployment_rise", "political_discontent", "social_unrest_risk"],
        "lag_months": {"unemployment_rise": 6, "political_discontent": 12, "social_unrest_risk": 24},
        "label": "地方经济衰退"
    },

    # ── 政治/社会（新增）──
    "polarization_surge": {
        "triggers": ["us_political_polarization > 75"],
        "consequences": ["political_discontent", "policy_gridlock", "fiscal_deadlock_risk"],
        "lag_months": {"political_discontent": 2, "policy_gridlock": 0, "fiscal_deadlock_risk": 6},
        "label": "政治极化加剧"
    },
    "policy_gridlock": {
        "triggers": ["polarization_surge"],
        "consequences": ["debt_ceiling_crisis", "govt_shutdown_risk"],
        "lag_months": {"debt_ceiling_crisis": 4, "govt_shutdown_risk": 3},
        "label": "政策僵局"
    },
    "fiscal_deadlock_risk": {
        "triggers": ["polarization_surge"],
        "consequences": ["debt_ceiling_crisis", "credit_rating_downgrade"],
        "lag_months": {"debt_ceiling_crisis": 6, "credit_rating_downgrade": 8},
        "label": "财政僵局"
    },
    "wealth_gap_alert": {
        "triggers": ["us_wealth_gap > 0.40"],
        "consequences": ["political_discontent", "populist_rise", "tax_reform_pressure"],
        "lag_months": {"political_discontent": 6, "populist_rise": 18, "tax_reform_pressure": 12},
        "label": "贫富差距警报"
    },

    # ── 终端叶子节点（标签补全）──
    "safe_haven_rush": {
        "triggers": ["inflation_fear", "global_contagion"],
        "consequences": [],
        "lag_months": {},
        "label": "避险资产涌入"
    },
    # ── 新增叶子节点（油价/人民币连锁链终点）──
    "pboc_intervention": {
        "triggers": ["cny_depreciation"],
        "consequences": [],
        "lag_months": {},
        "label": "央行干预汇市"
    },
    "em_currency_contagion": {
        "triggers": ["cny_depreciation"],
        "consequences": [],
        "lag_months": {},
        "label": "新兴货币传染"
    },
    "china_stock_pressure": {
        "triggers": ["china_capital_outflow"],
        "consequences": [],
        "lag_months": {},
        "label": "A股承压"
    },
    "china_bond_selloff": {
        "triggers": ["china_capital_outflow"],
        "consequences": [],
        "lag_months": {},
        "label": "中国债市抛售"
    },
    "fx_reserve_decline": {
        "triggers": ["china_capital_outflow"],
        "consequences": [],
        "lag_months": {},
        "label": "外储下降"
    },
    "energy_sector_default_risk": {
        "triggers": ["oil_collapse"],
        "consequences": [],
        "lag_months": {},
        "label": "能源企业违约风险"
    },
    "fed_hike_pressure": {
        "triggers": ["inflation_fear", "inflation_imported"],
        "consequences": [],
        "lag_months": {},
        "label": "Fed加息压力回升"
    },
    "usd_reserve_decline": {
        "triggers": ["currency_confidence_erosion"],
        "consequences": [],
        "lag_months": {},
        "label": "美元储备份额下降"
    },
    "alternative_reserve_search": {
        "triggers": ["currency_confidence_erosion", "de_dollarization_talk"],
        "consequences": [],
        "lag_months": {},
        "label": "替代储备货币搜索"
    },
    "corporate_hiring_freeze": {
        "triggers": ["recession_signal"],
        "consequences": [],
        "lag_months": {},
        "label": "企业招聘冻结"
    },
    "investment_decline": {
        "triggers": ["recession_signal"],
        "consequences": [],
        "lag_months": {},
        "label": "投资下降"
    },
    "debt_ceiling_crisis": {
        "triggers": ["policy_gridlock", "fiscal_deadlock_risk"],
        "consequences": [],
        "lag_months": {},
        "label": "债务上限危机"
    },
    "govt_shutdown_risk": {
        "triggers": ["policy_gridlock"],
        "consequences": [],
        "lag_months": {},
        "label": "政府停摆风险"
    },
    "lending_standards_tighten": {
        "triggers": ["bank_margin_pressure"],
        "consequences": [],
        "lag_months": {},
        "label": "贷款标准收紧"
    },
    "credit_freeze": {
        "triggers": ["small_bank_stress"],
        "consequences": [],
        "lag_months": {},
        "label": "信贷冻结"
    },
    "panic_contagion": {
        "triggers": ["bank_failure_risk"],
        "consequences": [],
        "lag_months": {},
        "label": "恐慌传染"
    },
    "fed_emergency": {
        "triggers": ["bank_failure_risk", "market_crash_risk"],
        "consequences": [],
        "lag_months": {},
        "label": "Fed紧急干预"
    },
    "deposit_flight": {
        "triggers": ["regional_bank_stress"],
        "consequences": ["consumer_confidence_drop", "credit_freeze"],
        "lag_months": {"consumer_confidence_drop": 2, "credit_freeze": 4},
        "label": "存款搬家"
    },
    "bank_loss_provision": {
        "triggers": ["bank_npl_concern", "corporate_default_rise"],
        "consequences": [],
        "lag_months": {},
        "label": "银行坏账拨备"
    },
    "social_unrest_risk": {
        "triggers": ["political_discontent", "regional_recession_china"],
        "consequences": [],
        "lag_months": {},
        "label": "社会动荡风险"
    },
    "credit_rating_downgrade": {
        "triggers": ["fiscal_deadlock_risk"],
        "consequences": [],
        "lag_months": {},
        "label": "信用评级下调"
    },
    "brics_currency_push": {
        "triggers": ["de_dollarization_talk"],
        "consequences": [],
        "lag_months": {},
        "label": "金砖货币推进"
    },
    "tax_reform_pressure": {
        "triggers": ["wealth_gap_alert"],
        "consequences": [],
        "lag_months": {},
        "label": "税制改革压力"
    },
    "policy_uncertainty": {
        "triggers": ["political_discontent"],
        "consequences": [],
        "lag_months": {},
        "label": "政策不确定性"
    },
    "fiscal_profligacy": {
        "triggers": ["populist_rise"],
        "consequences": [],
        "lag_months": {},
        "label": "财政纪律松弛"
    },
    "supply_chain_disruption": {
        "triggers": ["trade_war_escalation"],
        "consequences": [],
        "lag_months": {},
        "label": "供应链断裂"
    },
    "currency_devaluation": {
        "triggers": ["central_bank_independence_threat"],
        "consequences": [],
        "lag_months": {},
        "label": "货币贬值"
    },
    "inflation_expectations_unhinged": {
        "triggers": ["central_bank_independence_threat"],
        "consequences": [],
        "lag_months": {},
        "label": "通胀预期失控"
    },
    "global_gdp_drag": {
        "triggers": ["trade_war_escalation"],
        "consequences": [],
        "lag_months": {},
        "label": "全球增长拖累"
    },
    "currency_collapse": {
        "triggers": ["bond_market_revolt"],
        "consequences": [],
        "lag_months": {},
        "label": "货币崩盘"
    },
    "austerity_forced": {
        "triggers": ["sovereign_debt_crisis"],
        "consequences": [],
        "lag_months": {},
        "label": "强制紧缩"
    },
    "imf_intervention": {
        "triggers": ["sovereign_debt_crisis"],
        "consequences": [],
        "lag_months": {},
        "label": "IMF干预"
    },
    "new_reserve_currency_race": {
        "triggers": ["reserve_status_questioned"],
        "consequences": [],
        "lag_months": {},
        "label": "新储备货币竞赛"
    },
    "global_order_reshuffle": {
        "triggers": ["reserve_status_questioned"],
        "consequences": [],
        "lag_months": {},
        "label": "全球秩序重组"
    },
    "retail_sales_decline": {
        "triggers": ["consumer_spending_slow"],
        "consequences": [],
        "lag_months": {},
        "label": "零售下滑"
    },
    "gdp_slowdown": {
        "triggers": ["consumer_spending_slow"],
        "consequences": [],
        "lag_months": {},
        "label": "GDP放缓"
    },
    "circuit_breaker_trigger": {
        "triggers": ["market_crash_risk"],
        "consequences": [],
        "lag_months": {},
        "label": "熔断触发"
    },
    "saving_rate_rise": {
        "triggers": ["consumer_confidence_drop"],
        "consequences": [],
        "lag_months": {},
        "label": "储蓄率上升"
    },
    "mortgage_default_rise": {
        "triggers": ["home_price_decline", "unemployment_rise"],
        "consequences": [],
        "lag_months": {},
        "label": "房贷违约上升"
    },
    "global_recession_risk": {
        "triggers": ["global_contagion"],
        "consequences": [],
        "lag_months": {},
        "label": "全球衰退风险"
    },
}


# ═══════════════════════════════════════════════════════
#  快照查询辅助
# ═══════════════════════════════════════════════════════

_SNAPSHOT_CACHE = None


def _snap() -> dict:
    global _SNAPSHOT_CACHE
    if _SNAPSHOT_CACHE is None:
        _SNAPSHOT_CACHE = get_snapshot()
    return _SNAPSHOT_CACHE


def _get_indicator(name: str) -> Optional[float]:
    snap = _snap()
    entry = snap.get(name, {})
    return entry.get("value")


def _check_condition(cond: str, indicators: dict) -> bool:
    """检查单个触发条件，如 'us_cpi > 3.5' 或 'fed_hike'（节点引用）"""
    parts = cond.split()
    if len(parts) == 1:
        # 节点引用 — 检查该节点是否已被激活
        return cond in indicators
    if len(parts) == 3:
        name, op, threshold_str = parts
        val = indicators.get(name)
        if val is None:
            return False
        threshold = float(threshold_str)
        if op == ">":
            return val > threshold
        if op == "<":
            return val < threshold
        if op == ">=":
            return val >= threshold
        if op == "<=":
            return val <= threshold
    return False


def _check_condition_with_strength(cond: str, indicators: dict, trends: dict = None) -> tuple:
    """V2: 检查条件 + 返回触发强度 (0-1)。

    不仅判断是否触发，还返回"有多触发"：
    - 刚过阈值 → 0.15~0.30 (弱触发，可能回摆)
    - 深度穿越 → 0.60~1.00 (强触发，趋势确定)
    - 逼近阈值 → 0.05~0.15 (预警，尚未触发但接近)

    Args:
        cond: 条件字符串如 'us_cpi > 3.5'
        indicators: 当前指标值
        trends: 可选趋势字典 {name: direction(±1) + velocity(0-1)}

    Returns:
        (is_triggered: bool, strength: float, detail: str)
    """
    if trends is None:
        trends = {}

    parts = cond.split()
    if len(parts) == 1:
        return (cond in indicators, 1.0 if cond in indicators else 0.0, "")

    if len(parts) == 3:
        name, op, threshold_str = parts
        val = indicators.get(name)
        if val is None:
            return (False, 0.0, f"{name} 数据缺失")

        threshold = float(threshold_str)
        trend = trends.get(name, {})

        # 计算距离（相对阈值的偏离比例）
        if threshold != 0:
            distance = (val - threshold) / abs(threshold)
        else:
            distance = val - threshold

        # 根据操作符判断方向
        if op == ">" or op == ">=":
            if op == ">=":
                is_met = val >= threshold
            else:
                is_met = val > threshold

            if is_met:
                # 已触发：强度取决于超过多少 + 趋势方向
                strength = min(1.0, 0.15 + abs(distance) * 2.5)
                # 趋势加成
                if trend.get("direction", 0) > 0:
                    strength = min(1.0, strength + 0.2 * trend.get("velocity", 0.5))
                detail = f"{name}={val:.1f}(>{threshold}) 强度={strength:.0%}"
            elif distance > -0.15:
                # 逼近但未触发 (在阈值15%距离内)
                strength = 0.05 + abs(distance) * 0.5
                detail = f"{name}={val:.1f} 逼近{threshold}(距{abs(distance)*100:.0f}%)"
            else:
                strength = 0.0
                detail = ""

        elif op == "<" or op == "<=":
            if op == "<=":
                is_met = val <= threshold
            else:
                is_met = val < threshold

            if is_met:
                strength = min(1.0, 0.15 + abs(distance) * 2.5)
                if trend.get("direction", 0) < 0:
                    strength = min(1.0, strength + 0.2 * trend.get("velocity", 0.5))
                detail = f"{name}={val:.1f}(<{threshold}) 强度={strength:.0%}"
            elif distance < 0.15:
                strength = 0.05 + abs(distance) * 0.5
                detail = f"{name}={val:.1f} 逼近{threshold}(距{abs(distance)*100:.0f}%)"
            else:
                strength = 0.0
                detail = ""

        return (is_met, strength, detail)

    return (False, 0.0, "")


def _compute_trends() -> dict:
    """从数据库计算各指标的短期趋势 (7天/30天方向和速度)。"""
    import sqlite3
    try:
        conn = sqlite3.connect(str(Path(__file__).parent.parent / "macro.db"))
        trends = {}
        # 对每个有触发条件的指标，计算7日和30日斜率
        indicators_of_interest = {
            "us_cpi", "china_cpi", "us_unemployment", "china_unemployment",
            "us_yield_curve", "gold", "china_debt_gdp", "china_pmi",
            "us_political_polarization", "us_wealth_gap", "china_wealth_gap",
            "us_sp500", "us_vixy", "us_fed_rate",
        }
        for ind in indicators_of_interest:
            rows = conn.execute(
                "SELECT value FROM macro_indicators WHERE indicator_name=? ORDER BY date DESC LIMIT 30",
                (ind,)
            ).fetchall()
            if len(rows) >= 5:
                values = [r[0] for r in rows]
                recent_avg = sum(values[:5]) / len(values[:5])
                older_avg = sum(values[-5:]) / len(values[-5:])
                if older_avg != 0:
                    direction = 1 if recent_avg > older_avg else -1
                    velocity = min(1.0, abs(recent_avg - older_avg) / abs(older_avg) * 5)
                    trends[ind] = {"direction": direction, "velocity": velocity}
        conn.close()
        return trends
    except:
        return {}


def detect_triggers_v2() -> list[dict]:
    """V2: 趋势感知触发检测 — 返回触发列表 + 强度 + 逼近预警。

    Returns:
        [{id, label, strength, is_approaching, detail}, ...]
    """
    snap = _snap()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    trends = _compute_trends()
    triggered = []

    for node_id, node in CAUSAL_GRAPH.items():
        prereqs = node.get("triggers", [])
        if not prereqs:
            continue

        all_met = True
        strengths = []
        details = []
        any_approaching = False

        for p in prereqs:
            is_met, strength, detail = _check_condition_with_strength(p, indicators, trends)
            if not is_met:
                if strength > 0.03:  # 逼近
                    any_approaching = True
                    details.append(detail)
                all_met = False
                break
            strengths.append(strength)
            if detail:
                details.append(detail)

        if all_met:
            avg_strength = sum(strengths) / len(strengths) if strengths else 1.0
            triggered.append({
                "id": node_id,
                "label": node.get("label", node_id),
                "strength": round(avg_strength, 3),
                "is_approaching": False,
                "detail": "; ".join(details),
            })
        elif any_approaching:
            # 添加为逼近预警
            triggered.append({
                "id": node_id,
                "label": node.get("label", node_id),
                "strength": 0.05,
                "is_approaching": True,
                "detail": "逼近: " + "; ".join(details),
            })

    return triggered


# ═══════════════════════════════════════════════════════
#  图遍历引擎
# ═══════════════════════════════════════════════════════

def traverse(seed_events: list[str]) -> list[dict]:
    """从种子事件出发，广度优先遍历因果图。

    Args:
        seed_events: 已触发的种子事件列表（如 ['yield_curve_inversion', 'gold_rally']）

    Returns:
        [{
            "event": 事件ID,
            "label": 中文标签,
            "expected_month": 从种子起的累计滞后月数,
            "chain": [导致链],
        }, ...]
    """
    snap = _snap()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    visited = set()
    queue = [(e, 0, [e]) for e in seed_events]  # (event, cumulative_lag, chain)
    timeline = []

    while queue:
        event, lag, chain = queue.pop(0)
        if event in visited:
            continue
        visited.add(event)

        node = CAUSAL_GRAPH.get(event, {})
        prereqs = node.get("triggers", [])

        # 对于非种子节点，检查先决条件（OR 逻辑：任一触发即满足）
        if event not in seed_events:
            if prereqs and not any(_check_condition(p, indicators) for p in prereqs):
                continue

        timeline.append({
            "event": event,
            "label": node.get("label", event),
            "expected_month": lag,
            "chain": chain,
        })

        # 将当前事件"激活"，后续节点可以依赖它
        indicators[event] = 1.0

        for consequence in node.get("consequences", []):
            if consequence not in visited:
                extra_lag = node.get("lag_months", {}).get(consequence, 1)
                queue.append((consequence, lag + extra_lag, chain + [consequence]))

    # 按时序分组
    timeline.sort(key=lambda x: x["expected_month"])
    return timeline


# ═══════════════════════════════════════════════════════
#  自动检测当前已触发的种子事件
# ═══════════════════════════════════════════════════════

def detect_triggers() -> list[str]:
    """从当前快照中自动检测已被触发的因果链种子事件。"""
    snap = _snap()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val

    triggered = []

    # 检查每个节点的触发条件
    for node_id, node in CAUSAL_GRAPH.items():
        prereqs = node.get("triggers", [])
        if not prereqs:
            continue

        # 检查所有先决条件（AND 关系）
        all_met = True
        for p in prereqs:
            if not _check_condition(p, indicators):
                all_met = False
                break

        if all_met:
            triggered.append(node_id)

    return triggered


def summarize_timeline(timeline: list[dict]) -> str:
    """生成可读的因果链推演报告。"""
    if not timeline:
        return "当前无已触发的因果链。"

    lines = [
        "═" * 55,
        "  Dalio 因果链条推演",
        "═" * 55
    ]

    # 按时段分组
    for horizon, horizon_name in [(6, "0-6个月"), (12, "6-12个月"), (24, "12-24个月"), (999, "24月+")]:
        group = [e for e in timeline if e["expected_month"] <= horizon
                 and e["expected_month"] > (0 if horizon == 6 else (6 if horizon == 12 else (12 if horizon == 24 else 24)))]
        if not group:
            continue

        lines.append(f"\n  ⏱ {horizon_name}:")
        for e in group:
            chain_str = " → ".join(CAUSAL_GRAPH.get(n, {}).get("label", n)
                                   for n in e["chain"])
            lines.append(f"    T+{e['expected_month']:<4} {e['label']:<14} | {chain_str}")

    return "\n".join(lines)


if __name__ == "__main__":
    _SNAPSHOT_CACHE = None  # 清除缓存
    triggers = detect_triggers()
    print(f"检测到 {len(triggers)} 个已触发种子事件:")
    for t in triggers:
        print(f"  • {CAUSAL_GRAPH[t]['label']} ({t})")

    timeline = traverse(triggers)
    print()
    print(summarize_timeline(timeline))
