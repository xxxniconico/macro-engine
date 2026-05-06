"""历史差异分析引擎 — Dalio 的「这次有什么不同」。

核心理念（深度研究视角1）：
找到相似的历史模板后，必须分析"这次有什么不同"——
否则就会被历史类比误导，忽略关键的结构性变化。

分析维度：
1. 技术变革 — AI/数字化以前不存在
2. 人口结构 — 老龄化 vs 年轻化
3. 地缘格局 — 单极/两极/多极
4. 金融系统 — 数字货币/影子银行/QE常态化
5. 政策工具 — 央行/财政工具箱变化
6. 信息速度 — 社交媒体/7×24新闻
7. 债务水平 — 绝对债务/GDP 远超历史
8. 气候/能源 — 绿色转型压力
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot
from engine.template_matcher import run_matcher


# ═══════════════════════════════════════════════════════
#  历史模板的结构性差异定义
# ═══════════════════════════════════════════════════════

DIFF_DIMENSIONS = [
    {
        "id": "technology",
        "label": "技术变革",
        "question": "当时有类似的技术革命吗？",
        "current": "AI/大模型革命正在重塑生产力。Transformer架构(2017)后，AI从实验室进入生产。2025年全球AI投资>$300B。这是历史上第一次'智能'本身成为可规模化的生产要素。",
        "weight": 0.20,
    },
    {
        "id": "demographics",
        "label": "人口结构",
        "question": "当时的人口结构与现在有何不同？",
        "current": "全球老龄化前所未有。中国人口已开始下降(2022峰值)，65+占比15%+。日本/欧洲更严重。历史上大多数危机时期人口结构偏年轻，劳动力充裕可缓冲冲击。",
        "weight": 0.15,
    },
    {
        "id": "geopolitics",
        "label": "地缘格局",
        "question": "当时是单极、两极还是多极世界？",
        "current": "从美国单极(1991-2016)向多极过渡。中美竞争+俄乌+中东重构。金砖扩容(6→11国)。全球南方崛起。上一次类似格局是1930年代(英美日德多极竞争)。",
        "weight": 0.15,
    },
    {
        "id": "financial_system",
        "label": "金融系统",
        "question": "当时的金融基础设施与现在有何不同？",
        "current": "QE/ZIRP成为常态工具。影子银行规模$65T+。加密货币$3T+市值。数字货币(CBDC)在试点。高频交易/算法交易主导流动性。金融传染速度远超历史任何时期。",
        "weight": 0.15,
    },
    {
        "id": "policy_tools",
        "label": "政策工具箱",
        "question": "当时的政策制定者有什么工具？现在有什么？",
        "current": "央行：QE/QT/负利率/YCC/前瞻指引/紧急贷款便利。财政：MMT理论被半实践(疫情期间$5T刺激)。但通胀制约降息空间。'财政主导'风险——央行独立性被侵蚀。",
        "weight": 0.10,
    },
    {
        "id": "information_speed",
        "label": "信息传播速度",
        "question": "信息在当时传播多快？现在呢？",
        "current": "社交媒体+7×24新闻→叙事形成和扩散速度×100。Reddit/WallStreetBets可以三天内逼空百亿基金。恐慌/贪婪的传播速度远超历史。'叙事驱动资金流'的循环加速了。",
        "weight": 0.10,
    },
    {
        "id": "debt_levels",
        "label": "债务绝对水平",
        "question": "当时的债务/GDP是多少？",
        "current": "全球债务$315T(333% GDP)。美国联邦债务$35T(124% GDP)。中国总债务297% GDP。大多数历史危机发生时的绝对债务水平远低于现在。'这次真的不一样'——因为债务确实更高。",
        "weight": 0.10,
    },
    {
        "id": "climate_energy",
        "label": "气候与能源",
        "question": "当时有气候转型压力吗？",
        "current": "全球能源转型$2T+/年投资。碳边境税(CBAM)改变贸易规则。极端天气频率×5。这是历史上第一次'物理约束'(碳排放上限)成为宏观变量。",
        "weight": 0.05,
    },
]


# ═══════════════════════════════════════════════════════
#  模板特定的差异分析（针对常见历史类比）
# ═══════════════════════════════════════════════════════

TEMPLATE_SPECIFIC_DIFFS = {
    "us_2013_taper": {
        "same": "Fed暗示退出宽松→新兴市场恐慌→但最终软着陆",
        "differences": [
            ("🔴 更危险", "2013年全球债务/GDP~250%，现在是333%——同样的紧缩，更大的脆弱性"),
            ("🔴 更危险", "2013年没有AI泡沫+VIX=28这样的混合信号"),
            ("🟢 更安全", "新兴市场现在外汇储备更充足，2013教训已被吸取"),
            ("🔴 更危险", "2013年中美关系正常，现在处于脱钩对抗中"),
        ],
    },
    "cn_2015_crash": {
        "same": "杠杆泡沫破裂→国家队救市→政策刺激→恢复",
        "differences": [
            ("🔴 更危险", "2015年居民杠杆率~40%，现在~65%——加杠杆空间更小"),
            ("🔴 更危险", "2015年房地产还在上升期，现在处于下行周期"),
            ("🟢 更安全", "2015年外汇储备流失严重，现在资本管制更成熟"),
            ("🔴 更危险", "2015年地方政府债务/GDP~40%，现在~80%+"),
        ],
    },
    "us_2000_dotcom": {
        "same": "科技股狂热→估值泡沫→破裂→衰退→Fed疯狂降息",
        "differences": [
            ("🔴 更危险", "2000年只有互联网泡沫，现在AI+黄金+国债+VIX多资产异常"),
            ("🟢 更安全", "2000年Fed利率6.5%有大量降息空间，现在4.33%空间更小"),
            ("🔴 更危险", "2000年全球化在巅峰，现在逆全球化/脱钩"),
            ("🟡 混合", "2000年科技股多数无盈利，现在Mag7有真实利润但估值也高"),
        ],
    },
    "us_2006_housing": {
        "same": "资产泡沫顶峰→信贷紧缩→危机→大衰退",
        "differences": [
            ("🟢 更安全", "2006年次贷是银行表内风险，现在影子银行风险更分散"),
            ("🔴 更危险", "2006年只有房地产，现在商业地产+私募信贷+衍生品多点开花"),
            ("🟢 更安全", "2006年后建立了Dodd-Frank/巴塞尔III，监管更强"),
            ("🔴 更危险", "2006年债务/GDP~60%，现在~124%——财政救援空间小得多"),
        ],
    },
    "cn_2018_trade_war": {
        "same": "关税升级→供应链重构→增长受损→部分脱钩",
        "differences": [
            ("🔴 更危险", "2018年只是贸易战，现在扩展到科技/金融/地缘全面对抗"),
            ("🟢 更安全", "2018年中国芯片自给率~15%，现在~35%+（部分领域）"),
            ("🔴 更危险", "2018年全球化仍为主流，现在'友岸外包/近岸外包'已成共识"),
            ("🟡 混合", "2018年有Phase 1协议降温，现在缺乏类似对话机制"),
        ],
    },
}


# ═══════════════════════════════════════════════════════
#  分析函数
# ═══════════════════════════════════════════════════════

def analyze_dimensions(snapshot: dict = None) -> list[dict]:
    """对8个差异维度进行当前状态评估。
    
    Returns:
        [{id, label, assessment, risk_direction, detail}, ...]
        risk_direction: "worse"(比历史更危险), "better"(更安全), "mixed"
    """
    if snapshot is None:
        snapshot = get_snapshot()
    
    all_indicators = {}
    for k in snapshot:
        val = snapshot[k].get("value")
        if val is not None:
            all_indicators[k] = val
    
    results = []
    
    for dim in DIFF_DIMENSIONS:
        # 评估这个维度是让当前形势比历史更危险还是更安全
        risk = "mixed"
        
        if dim["id"] == "debt_levels":
            debt = all_indicators.get("china_debt_gdp", 200)
            if debt > 300:
                risk = "worse"
                detail = f"中国债务{debt}%远超历史危机均值(~200%)"
            elif debt > 250:
                risk = "worse"
                detail = f"债务{debt}%处于历史高位"
            else:
                risk = "better"
                detail = "债务水平可控"
        
        elif dim["id"] == "demographics":
            # 全球化老龄化 → 长期增长潜力下降 → 更难走出危机
            risk = "worse"
            detail = "全球老龄化(中国人口下降)→劳动力萎缩→潜在增长率↓→债务更难偿还"
        
        elif dim["id"] == "geopolitics":
            polar = all_indicators.get("us_political_polarization", 70)
            vix = all_indicators.get("us_vixy", 20)
            if polar > 80 and vix > 25:
                risk = "worse"
                detail = f"极化{polar}+VIX={vix}→多极对抗加剧→协调应对危机更难"
            else:
                risk = "mixed"
                detail = "多极竞争但仍有对话渠道"
        
        elif dim["id"] == "technology":
            risk = "mixed"
            detail = "AI可能提升生产率(好)但也可能大规模替代就业(坏)——历史上无先例"
        
        elif dim["id"] == "financial_system":
            risk = "worse"
            detail = "影子银行$65T+加密货币+高频交易→传染速度×100→监管盲区大"
        
        elif dim["id"] == "policy_tools":
            fed_rate = all_indicators.get("us_fed_rate", 4)
            if fed_rate > 3:
                risk = "better"
                detail = f"Fed有{int(fed_rate*100)}bp降息空间+QE/QT/紧急工具"
            else:
                risk = "worse"
                detail = "降息空间耗尽→政策工具枯竭风险"
        
        elif dim["id"] == "information_speed":
            risk = "worse"
            detail = "社交媒体加速叙事形成→'叙事→资金流→价格'循环速度×100→更容易形成自我实现的恐慌"
        
        elif dim["id"] == "climate_energy":
            risk = "mixed"
            detail = "绿色转型是长期增长引擎(好)但转型过程可能导致能源通胀(坏)"
        
        results.append({
            "id": dim["id"],
            "label": dim["label"],
            "question": dim["question"],
            "current_state": dim["current"][:150],
            "risk_direction": risk,
            "detail": detail,
            "weight": dim["weight"],
        })
    
    return results


def analyze_template_diff(match_result: dict) -> dict:
    """对最佳匹配模板做差异分析。
    
    Returns:
        {template_name, similarity, same_situation, specific_diffs, generic_dims, net_assessment}
    """
    if not match_result or not match_result.get("matches"):
        return {"error": "无匹配模板"}
    
    top = match_result["matches"][0]
    template_id = _infer_template_id(top["name"])
    
    # 模板特定差异
    specific = TEMPLATE_SPECIFIC_DIFFS.get(template_id, {})
    
    # 通用维度
    generic_dims = analyze_dimensions()
    
    # 净评估
    worse_count = 0
    better_count = 0
    
    if specific.get("differences"):
        for direction, _ in specific["differences"]:
            if "更危险" in direction:
                worse_count += 1
            elif "更安全" in direction:
                better_count += 1
    
    # 加上通用维度
    for dim in generic_dims:
        if dim["risk_direction"] == "worse":
            worse_count += 1
        elif dim["risk_direction"] == "better":
            better_count += 1
    
    total = worse_count + better_count
    if total == 0:
        net = "难判断"
    elif worse_count > better_count * 1.5:
        net = "🔴 比历史更危险"
    elif worse_count > better_count:
        net = "🟡 略比历史危险"
    elif better_count > worse_count * 1.5:
        net = "🟢 比历史更安全"
    else:
        net = "🟡 混合——有些更危险，有些更安全"
    
    return {
        "template_name": top["name"],
        "similarity": top["similarity"],
        "template_period": f"{top.get('country','')} {top.get('period','')}",
        "same_situation": specific.get("same", "当前与历史模板高度相似"),
        "specific_diffs": specific.get("differences", []),
        "generic_dims": [
            {"label": d["label"], "risk": d["risk_direction"], "detail": d["detail"]}
            for d in generic_dims
        ],
        "net_assessment": net,
        "worse_count": worse_count,
        "better_count": better_count,
    }


def _infer_template_id(name: str) -> str:
    """从模板名称推断 template_id。"""
    mapping = {
        "taper": "us_2013_taper",
        "2013": "us_2013_taper",
        "股灾": "cn_2015_crash",
        "2015": "cn_2015_crash",
        "互联网": "us_2000_dotcom",
        "dotcom": "us_2000_dotcom",
        "2000": "us_2000_dotcom",
        "房地产": "us_2006_housing",
        "2006": "us_2006_housing",
        "贸易战": "cn_2018_trade_war",
        "2018": "cn_2018_trade_war",
    }
    name_lower = name.lower()
    for key, tid in mapping.items():
        if key in name_lower:
            return tid
    return "unknown"


# ═══════════════════════════════════════════════════════
#  主函数
# ═══════════════════════════════════════════════════════

def run_diff_analysis() -> dict:
    """运行完整的历史差异分析。
    
    Returns:
        {template_match: {...}, diff_analysis: {...}, summary: str}
    """
    # 获取模板匹配结果
    match_result = run_matcher()
    
    if match_result.get("message"):
        return {"error": match_result["message"]}
    
    # 差异分析
    diff = analyze_template_diff(match_result)
    
    # 摘要
    summary = (
        f"最像「{diff.get('template_name','?')}」({diff.get('similarity',0)*100:.0f}%相似) | "
        f"{diff.get('net_assessment','?')} "
        f"(更危险×{diff.get('worse_count',0)} vs 更安全×{diff.get('better_count',0)})"
    )
    
    return {
        "template_match": {
            "top5": match_result["matches"][:5],
            "path_prediction": match_result.get("path_prediction", {}),
        },
        "diff_analysis": diff,
        "summary": summary,
    }


# ═══════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    result = run_diff_analysis()
    
    if "error" in result:
        print(f"⚠️ {result['error']}")
    else:
        diff = result["diff_analysis"]
        print(f"\n🔍 历史差异分析")
        print(f"  最佳匹配: {diff['template_name']} ({diff['similarity']*100:.0f}%)")
        print(f"  历史背景: {diff['template_period']}")
        print(f"  相似之处: {diff['same_situation']}")
        print(f"\n  ═══ 这次有什么不同？═══")
        
        if diff.get("specific_diffs"):
            print(f"\n  📌 模板特定差异:")
            for direction, detail in diff["specific_diffs"]:
                print(f"    {direction}: {detail}")
        
        print(f"\n  📐 8维结构差异:")
        for d in diff["generic_dims"]:
            icon = {"worse":"🔴","better":"🟢","mixed":"🟡"}.get(d["risk"],"⚪")
            print(f"    {icon} {d['label']}: {d['detail'][:80]}")
        
        print(f"\n  ═══ 净评估 ═══")
        print(f"  {diff['net_assessment']}")
        print(f"  更危险: {diff['worse_count']} | 更安全: {diff['better_count']}")
        print(f"\n  📊 {result['summary']}")
