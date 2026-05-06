"""第一性原理引擎 — Dalio 视角8：「拆到最底层再思考」。

核心理念（深度研究视角8）：
"如果你能看透本质，你就不会被表象迷惑。"
—— Dalio 从大宗商品交易员训练出的思维方式

方法：
1. 把一个复杂的宏观问题拆到最底层——每一笔交易、每一个决策的动机
2. 用"交易视角"理解经济：经济 = 所有交易的总和
3. 从第一性原理出发推断，而不是从中间概念出发

预设分析主题：
- 美联储加息的影响
- 中美贸易战
- AI革命
- 去美元化
- 中国房地产
- 黄金为什么涨
- 为什么曲线倒挂是衰退信号
- 债务危机如何形成
"""

import sys
from pathlib import Path
from typing import Optional
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, DB_PATH


# ═══════════════════════════════════════════════════════
#  第一性原理链定义
#  格式: topic → [step1, step2, ..., root_cause]
#  每一步都是"用更基础的术语重新表述"
# ═══════════════════════════════════════════════════════

CHAINS = {
    "fed_rate_hike": {
        "topic": "美联储加息如何传导到实体经济？",
        "kaomoji": "🏦→💸→🛒→📉",
        "steps": [
            {
                "level": 1,
                "label": "市场层",
                "insight": "Fed加息→联邦基金利率↑",
                "deeper": "Fed 通过调整银行间拆借利率来控制货币价格",
            },
            {
                "level": 2,
                "label": "银行层",
                "insight": "银行间拆借利率↑→银行融资成本↑→贷款利率↑",
                "deeper": "银行的商业模式是借短贷长，融资成本上升直接压缩利差",
            },
            {
                "level": 3,
                "label": "企业层",
                "insight": "贷款利率↑→企业借钱变贵→资本开支减少",
                "deeper": "企业做投资决策时比较IRR和资金成本，加息让很多项目变得不划算",
            },
            {
                "level": 4,
                "label": "就业层",
                "insight": "资本开支减少→招聘冻结→失业率↑",
                "deeper": "企业不再扩张→不需要新员工→甚至裁员",
            },
            {
                "level": 5,
                "label": "消费层",
                "insight": "失业率↑+信用卡利率↑→消费者可支配收入↓→消费↓",
                "deeper": "消费是GDP的70%，消费下降=经济减速",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**货币的价格上升→所有用货币计价的活动都变得更贵→经济活动减速**",
                "deeper": "经济=所有交易的总和。加息=每笔交易的成本变高=交易总量下降=GDP下降。这就是为什么加息能抑制通胀——它通过让所有人'更穷'来降低总需求。",
            },
        ],
        "current_relevance": "Fed利率4.33%，通胀3%+，曲线倒挂——Fed在'让所有人更穷'和'避免衰退'之间走钢丝",
    },
    
    "us_china_trade_war": {
        "topic": "中美贸易战如何影响普通人？",
        "kaomoji": "🇺🇸⚔️🇨🇳→📦→💰→😟",
        "steps": [
            {
                "level": 1,
                "label": "政策层",
                "insight": "关税→进口商品价格↑",
                "deeper": "关税本质是政府对进口商品征税。这个税最终由进口国的消费者支付——不是出口国。",
            },
            {
                "level": 2,
                "label": "价格层",
                "insight": "商品价格↑→消费者实际购买力↓",
                "deeper": "花更多钱买同样的东西→可用于其他消费的钱减少",
            },
            {
                "level": 3,
                "label": "企业层",
                "insight": "供应链重构→企业成本↑→要么涨价要么裁员",
                "deeper": "从中国采购→越南/墨西哥/印度→成本更高→利润降低",
            },
            {
                "level": 4,
                "label": "宏观层",
                "insight": "两边消费者同时变穷→全球总需求↓→全球增长减速",
                "deeper": "贸易不是零和博弈。贸易战=双方都设置障碍→双方都变穷",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**贸易=用我擅长的换你擅长的。贸易战=双方拒绝交换→双方都只能用自己不太擅长的方式生产→效率下降→都变穷**",
                "deeper": "比较优势原理：即使一个国家什么都比另一个国家强，专注做自己'最擅长'的然后交换，仍然对双方都有利。关税=破坏这个交换机制。",
            },
        ],
        "current_relevance": "关税已从贸易扩展到科技(芯片禁令)、金融(SWIFT制裁风险)、投资(CFIUS审查)。脱钩从边缘走向核心。",
    },
    
    "ai_revolution": {
        "topic": "AI革命到底改变了什么？",
        "kaomoji": "🤖→⚡→📈/📉",
        "steps": [
            {
                "level": 1,
                "label": "技术层",
                "insight": "LLM可以生成类人文本/代码/图像",
                "deeper": "Transformer架构让机器'理解'了语言的统计规律，但这不是真正的'理解'而是模式匹配",
            },
            {
                "level": 2,
                "label": "生产层",
                "insight": "AI=一种新的生产要素。和蒸汽机/电力/互联网一样，它让'单位投入获得更多产出'成为可能",
                "deeper": "每次技术革命都遵循同样模式：新技术→生产率提升→旧岗位消失+新岗位诞生→社会阵痛→最终整体更富",
            },
            {
                "level": 3,
                "label": "分配层",
                "insight": "AI的核心问题不是'会不会提升生产率'，而是'生产率提升的好处归谁'",
                "deeper": "如果好处全部归资本(拥有AI的公司)，劳动者反而变穷→贫富差距爆炸→社会不稳定",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**AI革命 = 智能从稀缺品变成可规模化生产的商品。历史上每次'稀缺变充裕'都带来爆炸性增长+巨大的分配冲突。**",
                "deeper": "蒸汽机让'体力'不再稀缺→工业革命。电力让'能源'不再稀缺→第二次工业革命。互联网让'信息'不再稀缺→信息革命。AI让'智能'不再稀缺→？？？但历史上每次这种变革，过渡期都伴随大规模失业+社会动荡(卢德运动、大萧条)，最终才走向更富裕。",
            },
        ],
        "current_relevance": "AI投资>$300B/年，Mag7市值>$15T。历史模式：狂热→泡沫→破裂→少数幸存者重塑世界(如2000互联网泡沫→Amazon/Google)。",
    },
    
    "de_dollarization": {
        "topic": "去美元化为什么在加速？",
        "kaomoji": "💵→📉→🥇→🌍",
        "steps": [
            {
                "level": 1,
                "label": "表面层",
                "insight": "各国央行在卖美债、买黄金——金价涨了47%",
                "deeper": "2022-2024年全球央行购金量创50年新高。中国连续18个月增持。",
            },
            {
                "level": 2,
                "label": "动机层",
                "insight": "为什么卖美债？因为持有美元资产不再'安全'了",
                "deeper": "美国冻结了俄罗斯$300B外汇储备(2022)→所有国家都意识到'美元资产可以被没收'→储备多元化成为国家安全问题",
            },
            {
                "level": 3,
                "label": "机制层",
                "insight": "储备货币的基石是'信任'——信任美国不会滥用货币霸权",
                "deeper": "当一个国家把美元当作储备，它相信：(1)美元不会大幅贬值 (2)美元资产不会被随意冻结 (3)美国会维护全球金融稳定",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**储备货币 = 全球都愿意持有你的欠条。去美元化 = 世界不再相信你的欠条能兑现。这不是经济问题——是信任问题。而信任一旦失去，重建需要几十年。**",
                "deeper": "历史上每一次储备货币更替(荷兰→英国→美国)都伴随：(1)原霸主战争/过度扩张 (2)新崛起力量挑战 (3)一次大的债务/货币危机作为催化剂。当前三条都在进行中。",
            },
        ],
        "current_relevance": "美元储备份额从2000年71%降至57%。金砖国家在推替代支付系统。但美元仍是贸易结算58%+金融交易88%——'去美元化'是趋势不是现实。",
    },
    
    "china_real_estate": {
        "topic": "中国房地产为什么是系统性风险？",
        "kaomoji": "🏠→💥→🏦→📉",
        "steps": [
            {
                "level": 1,
                "label": "规模层",
                "insight": "房地产相关产业占中国GDP~25-30%",
                "deeper": "不仅是开发商——钢铁、水泥、家电、装修、银行按揭、地方政府土地出让金——全部连在一起",
            },
            {
                "level": 2,
                "label": "财富层",
                "insight": "中国家庭70%财富在房产里",
                "deeper": "房价下跌=70%的家庭财富缩水→消费者不敢花钱→内需萎缩",
            },
            {
                "level": 3,
                "label": "银行层",
                "insight": "银行贷款~40%与房地产相关",
                "deeper": "开发商违约→银行坏账↑→银行惜贷→企业融资更难→经济进一步下行→更多违约→恶性循环",
            },
            {
                "level": 4,
                "label": "财政层",
                "insight": "地方政府~40%收入来自土地出让",
                "deeper": "土地卖不出去→地方财政缺口→缩减公共服务/拖欠工资→社会压力",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**房地产不是'一个行业'——它是中国经济的资产负债表本身。房价下跌=资产负债表衰退。这不仅仅是'房市不好'，这是全民、全行业、全政府的资产都在缩水。**",
                "deeper": "辜朝明的'资产负债表衰退'理论：当资产价格暴跌，企业和家庭从'利润最大化'转向'债务最小化'→即使利率为零也不借钱→经济长期停滞。日本1990-2010就是前车之鉴。",
            },
        ],
        "current_relevance": "房地产投资从2021峰值下降~30%。恒大/碧桂园违约。但2024年以来政策力度空前：降首付、降利率、白名单、政府收储。软着陆还是硬着陆仍有变数。",
    },
    
    "gold_rally": {
        "topic": "黄金为什么涨了这么多？",
        "kaomoji": "🥇→📈→💵📉→😰",
        "steps": [
            {
                "level": 1,
                "label": "价格层",
                "insight": "金价年涨47%→这不是'投资黄金有收益'，这是'持有美元在贬值'",
                "deeper": "黄金不产生利息。买黄金的唯一理由是你认为其他资产（特别是法定货币）会贬值。",
            },
            {
                "level": 2,
                "label": "动机层",
                "insight": "谁在买？央行+机构+散户，三类买家同时涌入",
                "deeper": "央行：去美元化+储备多元化。机构：对冲地缘风险+通胀。散户：FOMO+避险叙事。三类买家动机不同但方向一致→完美风暴。",
            },
            {
                "level": 3,
                "label": "信任层",
                "insight": "金价上涨=对法定货币体系的信任在下降",
                "deeper": "黄金是5000年来的'最终货币'。当人们对政府发行的货币失去信心时，就会回到黄金。",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**金价上涨 = 全球在用脚投票：'我们不相信美元/欧元/日元能保值'。黄金没有基本面——它的'基本面'就是人们对法币体系的不信任程度。**",
                "deeper": "历史上每次金价暴涨都对应着货币体系的危机时刻：1971布雷顿森林解体→金价$35→$850。2008金融危机+QE→金价$700→$1900。2022至今：俄资产冻结+美债飙升+去美元化→金价$1800→$4700+。",
            },
        ],
        "current_relevance": "金价$4721，年涨47%。如果突破$5000将是心理里程碑。但黄金已是'拥挤交易'——所有人都在船上时，反转也可能很剧烈。",
    },
    
    "yield_curve_inversion": {
        "topic": "为什么曲线倒挂是衰退信号？",
        "kaomoji": "📉📈→⚠️→📉📉",
        "steps": [
            {
                "level": 1,
                "label": "定义层",
                "insight": "曲线倒挂=短期利率>长期利率→2年期国债收益率>10年期",
                "deeper": "正常情况：长期利率>短期利率（因为锁定资金更久需要补偿→期限溢价）",
            },
            {
                "level": 2,
                "label": "信号层",
                "insight": "倒挂=市场在说'短期内经济会很差→Fed会被迫降息→所以长期利率反而更低'",
                "deeper": "市场用真金白银在押注衰退——这不是经济学家在预测，是数万亿美元在定价",
            },
            {
                "level": 3,
                "label": "机制层",
                "insight": "倒挂本身也'制造'衰退：银行借短贷长→短端利率>长端→利差消失→银行不赚钱→收缩信贷→经济减速",
                "deeper": "这就是倒挂'自我实现'的机制——不只是预测衰退，它本身就是衰退的加速器",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**利率曲线的形状 = 全市场对未来经济增长的集体押注。倒挂 = 市场用数万亿美元押注'未来会比现在更差'。这不是观点，是价格。价格是市场唯一的诚实语言。**",
                "deeper": "自1950年代以来，每次曲线倒挂后都出现了衰退（除了1998年一次短暂的假信号）。倒挂→衰退平均滞后12-18个月。当前倒挂已持续~20个月。",
            },
        ],
        "current_relevance": "2Y/10Y利差=0.87（倒挂中），已持续近2年。这是1970年代以来最长的一次倒挂。衰退是否已经'被推迟'而非'被避免'？",
    },
    
    "debt_crisis_mechanics": {
        "topic": "债务危机到底是怎样发生的？",
        "kaomoji": "💳→📈→💥→🏦",
        "steps": [
            {
                "level": 1,
                "label": "积累期",
                "insight": "借钱→消费/投资→经济增长→收入增加→可以借更多→循环",
                "deeper": "债务本身不是坏事——它让今天的花费可以创造明天的收入。问题在于：债务的增长速度超过了收入的增长速度。",
            },
            {
                "level": 2,
                "label": "临界点",
                "insight": "当新增债务不再产生足够的收入来还本付息时→临界点到来",
                "deeper": "每借$1产生$0.8的GDP增长→每次借钱净增$0.2的债务负担→日积月累→还本付息占收入比例越来越高",
            },
            {
                "level": 3,
                "label": "触发",
                "insight": "某个冲击（利率上升/收入下降/信心丧失）→无法再融资→违约",
                "deeper": "债务危机的本质是'流动性危机'→'偿付能力危机'的切换。一开始只是'暂时还不上'→如果没人愿意再借钱→变成'永远还不上'",
            },
            {
                "level": "root",
                "label": "第一性原理",
                "insight": "**债务 = 把未来的收入挪到今天花。债务危机 = 未来没有足够收入来偿还过去的挪借。解决只有四种方式：(1)紧缩→通缩 (2)违约→赖账 (3)印钱→通胀 (4)再分配→加税。Dalio的'漂亮去杠杆'=四种方式的恰当组合。**",
                "deeper": "理解债务危机最关键的一个概念：一个人的债务是另一个人的资产。当债务无法偿还时，不仅是借款人破产——债权人的资产也消失了。这就是为什么债务危机会传染。",
            },
        ],
        "current_relevance": "全球债务$315T(333% GDP)。美国$35T(124% GDP)每年利息支出>$1T超过军费。中国297%。日本260%。世界从未在如此高的债务水平上运行过。",
    },
}


# ═══════════════════════════════════════════════════════
#  自动关联：当前数据触发了哪些第一性原理链
# ═══════════════════════════════════════════════════════

THEME_TRIGGERS = {
    "fed_rate_hike": ["us_fed_rate > 3.5", "us_yield_curve < 0.95"],
    "us_china_trade_war": ["us_political_polarization > 75", "us_vixy > 25"],
    "ai_revolution": ["us_sp500 > 5500", "us_vixy > 20"],
    "de_dollarization": ["gold > 4500", "usd_reserve_share < 58"],
    "china_real_estate": ["china_debt_gdp > 280", "china_pmi < 51"],
    "gold_rally": ["gold > 4000"],
    "yield_curve_inversion": ["us_yield_curve < 0.95"],
    "debt_crisis_mechanics": ["china_debt_gdp > 290", "us_debt_gdp > 120"],
}


def get_active_chains(snapshot: dict = None) -> list[dict]:
    """根据当前数据自动匹配最相关的第一性原理链。
    
    Returns:
        按相关性排序的链列表
    """
    if snapshot is None:
        snapshot = get_snapshot()
    
    indicators = {}
    for k in snapshot:
        val = snapshot[k].get("value")
        if val is not None:
            indicators[k] = val
    
    active = []
    
    for chain_id, conditions in THEME_TRIGGERS.items():
        chain = CHAINS.get(chain_id)
        if not chain:
            continue
        
        # 检查触发条件
        trig_count = 0
        total_cond = len(conditions)
        
        for cond in conditions:
            parts = cond.split()
            if len(parts) == 3:
                name, op, threshold_str = parts
                val = indicators.get(name)
                if val is None:
                    continue
                threshold = float(threshold_str)
                if op == ">" and val > threshold:
                    trig_count += 1
                elif op == "<" and val < threshold:
                    trig_count += 1
        
        # 至少一半条件满足
        if trig_count >= max(1, total_cond // 2):
            # 获取该链的根洞察
            root = next((s for s in chain["steps"] if s["level"] == "root"), None)
            
            active.append({
                "id": chain_id,
                "topic": chain["topic"],
                "kaomoji": chain["kaomoji"],
                "trigger_ratio": trig_count / max(total_cond, 1),
                "root_insight": root["insight"] if root else "",
                "current_relevance": chain["current_relevance"],
                "step_count": len(chain["steps"]),
            })
    
    # 按触发比例排序
    active.sort(key=lambda x: x["trigger_ratio"], reverse=True)
    return active


def get_chain_detail(chain_id: str) -> Optional[dict]:
    """获取特定链的完整分解。"""
    return CHAINS.get(chain_id)


def analyze() -> dict:
    """运行第一性原理分析。
    
    Returns:
        {active_chains: [...], summary: str}
    """
    active = get_active_chains()
    
    # 摘要
    if active:
        topics = " → ".join(c["kaomoji"] for c in active[:4])
        summary = f"当前触发 {len(active)}/8 条第一性原理链: {topics}"
    else:
        summary = "当前无数据触发第一性原理链"
    
    return {
        "date": date.today().isoformat(),
        "active_chains": active,
        "all_chains": [
            {"id": cid, "topic": c["topic"], "kaomoji": c["kaomoji"]}
            for cid, c in CHAINS.items()
        ],
        "summary": summary,
    }


# ═══════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--chain", type=str, help="查看特定链的完整分解")
    parser.add_argument("--list", action="store_true", help="列出所有预设链")
    args = parser.parse_args()
    
    if args.list:
        print("\n📚 第一性原理链库 (8条):")
        for cid, c in CHAINS.items():
            print(f"  {c['kaomoji']} {cid}: {c['topic']}")
        print()
        sys.exit(0)
    
    if args.chain:
        chain = get_chain_detail(args.chain)
        if chain:
            print(f"\n{chain['kaomoji']} {chain['topic']}")
            print(f"  📍 当前相关性: {chain['current_relevance']}")
            print(f"\n  分解:")
            for step in chain["steps"]:
                if step["level"] == "root":
                    print(f"\n  ═══ 第一性原理 ═══")
                else:
                    print(f"\n  L{step['level']} [{step['label']}]")
                print(f"  {step['insight']}")
                print(f"  → {step['deeper']}")
        else:
            print(f"⚠️ 未找到链: {args.chain}")
            print(f"  可用: {', '.join(CHAINS.keys())}")
        sys.exit(0)
    
    result = analyze()
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n🧠 第一性原理分析 — {result['date']}")
        print(f"  {result['summary']}")
        
        for i, c in enumerate(result["active_chains"], 1):
            print(f"\n  {i}. {c['kaomoji']} {c['topic']}")
            print(f"     触发度: {c['trigger_ratio']:.0%}")
            print(f"     根洞察: {c['root_insight'][:100]}...")
        
        print(f"\n  💡 运行 `--chain <id>` 查看完整分解")
