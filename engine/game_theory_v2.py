"""多方博弈引擎 V2 — 动态博弈树 + 多步模拟 + 历史追踪。

V2 新增（P1）：
1. 动态博弈树 — 模拟"A出手→B应对→A再应对"的多步博弈
2. 博弈历史追踪 — SQLite 记录各玩家实际动作变化
3. 策略空间分析 — 可选策略 × 当前约束 → 最优策略推断

Dalio 的核心问题：
不是问"我认为会发生什么"，而是问"各方在各自约束下会怎么做？各方行为的加总效应是什么？"
"""

# ═══════════════════════════════════════════════════════
#  Sigmoid 可行性函数 — 替代硬编码 if/else
# ═══════════════════════════════════════════════════════

import math

def sigmoid_feasibility(value: float, threshold: float, steepness: float = 1.0,
                        direction: str = "below") -> float:
    """Sigmoid 平滑可行性: 将"指标值 vs 阈值"映射为连续的 0-1 可行性。

    Args:
        value: 当前指标值
        threshold: 临界阈值
        steepness: 陡峭度 (越高过渡越锐利，默认1.0)
        direction:
          "below" → 值越低可行性越高 (如 CPI低→降息可行)
          "above" → 值越高可行性越高 (如 PMI高→收紧可行)
          "midpoint" → 越接近阈值越可行 (如 debt=300% 刚好可接受)

    Returns:
        0.0 ~ 1.0 的可行性得分
    """
    diff = value - threshold
    if direction == "below":
        x = -diff * steepness
    elif direction == "above":
        x = diff * steepness
    elif direction == "midpoint":
        x = -abs(diff) * steepness
    else:
        x = diff * steepness
    return 1.0 / (1.0 + math.exp(-x))

import sys
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, DB_PATH

# 复用 V1 的参与方定义和关系矩阵
from engine.game_theory import PLAYERS, RELATIONS


# ═══════════════════════════════════════════════════════
#  策略空间定义 — 每个玩家在当前约束下可选的动作
# ═══════════════════════════════════════════════════════

def get_strategy_space(indicators: dict) -> dict:
    """为每个玩家生成当前可用的策略空间。
    
    Returns:
        {player_id: [{action, label, feasibility, rationale}, ...]}
    """
    spaces = {}
    
    # ── 美联储 ──
    fed_rate = indicators.get("us_fed_rate", 4.33)
    cpi = indicators.get("us_cpi", 3)
    unemp = indicators.get("us_unemployment", 5)
    curve = indicators.get("us_yield_curve", 1)
    
    fed_strategies = [
        {
            "action": "hold",
            "label": "维持利率不变",
            "feasibility": round(1.0 - sigmoid_feasibility(cpi, 3.2, steepness=2.0, direction="below") * 0.6, 2),
            "rationale": f"CPI={cpi}%+就业{unemp}%→不急于行动",
        },
        {
            "action": "cut_25bp",
            "label": "降息25bp",
            "feasibility": round(sigmoid_feasibility(cpi, 3.5, steepness=1.5, direction="below") * 0.8, 2),
            "rationale": "曲线倒挂→需要正常化，但通胀仍是障碍",
        },
        {
            "action": "cut_50bp",
            "label": "紧急降息50bp",
            "feasibility": round(sigmoid_feasibility(curve, 0.85, steepness=3.0, direction="below") * 0.3, 2),
            "rationale": "只有深度倒挂或市场崩盘才会触发",
        },
        {
            "action": "hike",
            "label": "加息",
            "feasibility": round(sigmoid_feasibility(cpi, 4.5, steepness=3.0, direction="above") * 0.2, 2),
            "rationale": "除非通胀二次飙升（极端场景）",
        },
    ]

    # 曲线倒挂加剧 → 降息压力连续增大
    curve_pressure = sigmoid_feasibility(curve, 0.95, steepness=3.0, direction="below")
    fed_strategies[1]["feasibility"] = round(min(0.85, fed_strategies[1]["feasibility"] + curve_pressure * 0.3), 2)
    if curve_pressure > 0.5:
        fed_strategies[1]["rationale"] += " | 曲线深度倒挂促Fed行动"
    
    spaces["fed"] = fed_strategies
    
    # ── 中国政府 ──
    pmi = indicators.get("china_pmi", 50)
    debt = indicators.get("china_debt_gdp", 297)
    cn_cpi = indicators.get("china_cpi", 1)
    
    cn_strategies = [
        {
            "action": "fiscal_stimulus",
            "label": "加大财政刺激（专项债+特别国债）",
            "feasibility": round(sigmoid_feasibility(debt, 310, steepness=0.5, direction="below") * 0.8, 2),
            "rationale": f"PMI={pmi}→需要托底，但债务{debt}%是硬约束",
        },
        {
            "action": "monetary_ease",
            "label": "降准降息",
            "feasibility": round(sigmoid_feasibility(cn_cpi, 2.5, steepness=1.5, direction="below") * 0.9, 2),
            "rationale": f"CPI={cn_cpi}%给了宽松空间",
        },
        {
            "action": "housing_rescue",
            "label": "房地产更大力度救助",
            "feasibility": round(sigmoid_feasibility(pmi, 51, steepness=2.0, direction="below") * 0.7, 2),
            "rationale": "房市是经济稳定器，救市有道德风险但不得不做",
        },
        {
            "action": "industrial_policy",
            "label": "产业升级（AI/新能源/芯片）",
            "feasibility": 0.9,
            "rationale": "长期战略，无论经济如何都推",
        },
    ]
    
    if pmi < 49:
        for s in cn_strategies[:3]:
            s["feasibility"] = min(1.0, s["feasibility"] + 0.15)
    
    spaces["china_gov"] = cn_strategies
    
    # ── 全球市场 ──
    vix = indicators.get("us_vixy", 28)
    sp500 = indicators.get("us_sp500", 6000)
    gold = indicators.get("gold", 4700)
    
    mkt_strategies = [
        {
            "action": "risk_on_ai",
            "label": "继续押注 AI/科技",
            "feasibility": 0.8,
            "rationale": "AI叙事→最强劲的主题投资",
        },
        {
            "action": "hedge_tail",
            "label": "增加尾部对冲（买VIX/黄金/债券）",
            "feasibility": 0.7 if vix > 25 else 0.3,
            "rationale": f"VIX={vix}→恐慌不低，对冲需求强",
        },
        {
            "action": "rotate_value",
            "label": "轮动到价值/防御板块",
            "feasibility": 0.5,
            "rationale": "科技估值过高→有轮动必要但动量太强",
        },
        {
            "action": "delever",
            "label": "降低杠杆/减仓",
            "feasibility": 0.3 if vix > 30 else 0.1,
            "rationale": "除非恐慌升级，否则不会主动减仓",
        },
    ]
    
    if vix > 30 and gold > 5000:
        mkt_strategies[3]["feasibility"] = 0.5  # 恐慌模式
    
    spaces["markets"] = mkt_strategies
    
    # ── 中国资本市场 ──
    cn_mkt_strategies = [
        {
            "action": "buy_dip",
            "label": "逢低布局（国家队视角）",
            "feasibility": 0.6,
            "rationale": "有托底需求但不愿拉升过快",
        },
        {
            "action": "follow_ai",
            "label": "跟随 AI 热点",
            "feasibility": 0.8,
            "rationale": "AI是唯一有赚钱效应的板块",
        },
        {
            "action": "wait",
            "label": "等待信号",
            "feasibility": 0.7,
            "rationale": "政策方向不明→观望",
        },
    ]
    spaces["china_markets"] = cn_mkt_strategies
    
    # ── 欧盟 ──
    eu_strategies = [
        {
            "action": "cut_rate",
            "label": "ECB 继续降息",
            "feasibility": 0.7,
            "rationale": "防衰退是首要任务",
        },
        {
            "action": "defense_spending",
            "label": "加大国防支出",
            "feasibility": 0.8,
            "rationale": "地缘紧张→军备升级",
        },
        {
            "action": "de_risk_china",
            "label": "对华去风险",
            "feasibility": 0.5,
            "rationale": "有政治压力但有经济成本",
        },
    ]
    spaces["eu"] = eu_strategies
    
    # ── 资源出口国 ──
    uso = indicators.get("us_uso", 80)
    
    resource_strategies = [
        {
            "action": "maintain_cuts",
            "label": "维持减产/高油价",
            "feasibility": 0.7,
            "rationale": f"油价{uso}→减产有利",
        },
        {
            "action": "de_dollarize",
            "label": "加速去美元贸易",
            "feasibility": 0.8,
            "rationale": "金砖机制→有替代方案",
        },
        {
            "action": "buy_gold",
            "label": "央行持续购金",
            "feasibility": 0.9,
            "rationale": "多元化储备是长期趋势",
        },
    ]
    spaces["commodity_producers"] = resource_strategies
    
    return spaces


# ═══════════════════════════════════════════════════════
#  动态博弈树 — 多步前瞻模拟
# ═══════════════════════════════════════════════════════

def simulate_game_tree(indicators: dict, depth: int = 3) -> dict:
    """构建博弈树：模拟多步博弈。
    
    核心逻辑：
    1. 从当前状态出发，假设每个玩家选最可行策略
    2. 策略产生"动作" → 影响市场/经济变量
    3. 下一轮玩家在变化后的环境中再做选择
    4. 重复 depth 次
    
    Returns:
        {
            "rounds": [{player_moves, market_impact, new_state}, ...],
            "terminal_scenarios": [...],
            "net_trajectory": str
        }
    """
    strategy_spaces = get_strategy_space(indicators)
    
    # 初始状态
    state = {
        "fed_rate": indicators.get("us_fed_rate", 4.33),
        "cpi": indicators.get("us_cpi", 3),
        "vix": indicators.get("us_vixy", 28),
        "gold": indicators.get("gold", 4700),
        "sp500": indicators.get("us_sp500", 6000),
        "china_pmi": indicators.get("china_pmi", 50),
        "china_debt": indicators.get("china_debt_gdp", 297),
        "yield_curve": indicators.get("us_yield_curve", 0.87),
        "reserve_share": indicators.get("usd_reserve_share", 57),
        "political_polarization": indicators.get("us_political_polarization", 80),
    }
    
    rounds = []
    
    for round_i in range(depth):
        moves = {}
        impacts = {}
        
        # ── Player 1: Fed ──
        if round_i == 0:
            # 第一轮：Fed 高概率选择降息25bp（曲线倒挂压力）
            if state["yield_curve"] < 0.85 or state["vix"] > 30:
                fed_move = "cut_25bp"
                fed_label = "降息25bp"
            else:
                fed_move = "hold"
                fed_label = "维持利率"
        else:
            # 后续轮：根据上一轮状态调整
            if state["fed_rate"] > 3 and state["yield_curve"] < 0.90:
                fed_move = "cut_25bp"
                fed_label = "降息25bp"
            else:
                fed_move = "hold"
                fed_label = "维持利率"
        
        moves["fed"] = fed_label
        
        # Fed 动作的影响
        if "cut" in fed_move:
            state["fed_rate"] -= 0.25
            state["sp500"] *= 1.03  # 利好股市
            state["cpi"] += 0.1  # 轻微通胀
            state["gold"] *= 1.02  # 利好黄金
            state["vix"] *= 0.9  # 恐慌下降
            impacts["fed"] = "降息→股市+3%, 黄金+2%, VIX↓"
        else:
            impacts["fed"] = "维持→市场中性"
        
        # ── Player 2: 中国政府 ──
        if state["china_pmi"] < 50:
            cn_move = "monetary_ease"
            cn_label = "降准降息"
        elif state["china_pmi"] < 51:
            cn_move = "fiscal_stimulus"
            cn_label = "财政刺激"
        else:
            cn_move = "industrial_policy"
            cn_label = "产业政策"
        
        moves["china_gov"] = cn_label
        
        if "ease" in cn_move or "stimulus" in cn_move:
            state["china_pmi"] += 0.3
            impacts["china_gov"] = "宽松→PMI微升+0.3"
        else:
            impacts["china_gov"] = "产业政策→结构性影响"
        
        # ── Player 3: 市场 ──
        if state["vix"] > 25 and state["gold"] > 4500:
            mkt_move = "hedge_tail"
            mkt_label = "增加对冲"
        elif state["sp500"] > 5500:
            mkt_move = "risk_on_ai"
            mkt_label = "AI风险偏好"
        else:
            mkt_move = "rotate_value"
            mkt_label = "轮动防御"
        
        moves["markets"] = mkt_label
        
        if "hedge" in mkt_move:
            state["gold"] *= 1.02
            state["vix"] *= 1.05  # 对冲需求拉升VIX
            impacts["markets"] = "对冲→黄金+2%, VIX+5%"
        elif "risk" in mkt_move:
            state["sp500"] *= 1.02
            impacts["markets"] = "风险偏好→股市+2%"
        
        # ── Player 4: 资源出口国 ──
        if state["gold"] > 4500:
            res_move = "buy_gold"
            res_label = "央行购金"
        else:
            res_move = "maintain_cuts"
            res_label = "维持减产"
        
        moves["commodity_producers"] = res_label
        
        if "gold" in res_move:
            state["gold"] *= 1.01  # 购金推高金价
            impacts["commodity_producers"] = "购金→金价+1%"
        
        # ── 美元信心（跨轮加总效应）──
        if round_i >= 1:
            # 去美元化逐步推进
            state["reserve_share"] -= 0.3
            state["gold"] *= 1.005
        
        rounds.append({
            "round": round_i + 1,
            "moves": moves,
            "impacts": impacts,
            "state_snapshot": {
                "Fed利率": f"{state['fed_rate']:.2f}%",
                "SP500": f"{state['sp500']:.0f}",
                "VIX": f"{state['vix']:.1f}",
                "黄金": f"${state['gold']:.0f}",
                "中国PMI": f"{state['china_pmi']:.1f}",
                "储备份额": f"{state['reserve_share']:.1f}%",
            },
        })
    
    # ── 终局场景 ──
    terminal_scenarios = derive_terminal_scenarios(state, indicators)
    
    # ── 净轨迹 ──
    net_trajectory = summarize_trajectory(rounds, state, indicators)
    
    return {
        "rounds": rounds,
        "terminal_scenarios": terminal_scenarios,
        "net_trajectory": net_trajectory,
        "strategy_space": strategy_spaces,
    }


def derive_terminal_scenarios(final_state: dict, initial: dict) -> list[dict]:
    """从博弈终局推导可能的宏观场景。"""
    scenarios = []
    
    # 场景A: 软着陆（最优）
    if final_state["fed_rate"] < initial.get("us_fed_rate", 4.33) - 0.5 \
       and final_state["vix"] < 25 \
       and final_state["china_pmi"] > 51:
        scenarios.append({
            "name": "🟢 软着陆",
            "probability": 0.25,
            "description": "Fed成功降息+中国稳增长→全球温和增长恢复",
            "triggers": "Fed精准降息 + 中国政策见效 + 地缘降温",
        })
    
    # 场景B: 滞胀
    if final_state["cpi"] > 3.5 and final_state["fed_rate"] < 3:
        scenarios.append({
            "name": "🔴 滞胀陷阱",
            "probability": 0.20,
            "description": "Fed过早降息→通胀反弹→被迫再加息→股债双杀",
            "triggers": "Fed政策错误 + 供给冲击 + 财政无纪律",
        })
    
    # 场景C: 去美元化加速
    if final_state["reserve_share"] < 56 and final_state["gold"] > 5000:
        scenarios.append({
            "name": "🔴 去美元化临界点",
            "probability": 0.25,
            "description": "储备份额跌破55%→美债需求崩溃→美元危机→全球秩序重组",
            "triggers": "金砖扩容 + 美政治极化 + 债务上限危机",
        })
    
    # 场景D: AI泡沫破裂
    if final_state["sp500"] > 6500 and final_state["vix"] > 28:
        scenarios.append({
            "name": "🟡 AI泡沫调整",
            "probability": 0.30,
            "description": "AI估值过高→科技股回调30-40%→拖累大盘→但非系统性危机",
            "triggers": "AI业绩不及预期 + 利率维持高位 + 盈利下修",
        })
    
    # 场景E: 中国硬着陆
    if final_state["china_pmi"] < 49 and final_state["china_debt"] > 300:
        scenarios.append({
            "name": "🔴 中国债务螺旋",
            "probability": 0.15,
            "description": "地方债+房地产→银行危机→经济失速→全球增长拖累",
            "triggers": "房地产二次探底 + 地方政府债券违约 + 资本外逃",
        })
    
    # 默认场景
    if not scenarios:
        scenarios.append({
            "name": "🟡 现状延续",
            "probability": 0.4,
            "description": "各方按兵不动→低增长+高波动持续",
        })
    
    return scenarios


def summarize_trajectory(rounds: list, final_state: dict, initial: dict) -> str:
    """总结博弈轨迹。"""
    parts = []
    
    # Fed路径
    fed_start = initial.get("us_fed_rate", 4.33)
    fed_end = final_state["fed_rate"]
    if fed_end < fed_start - 0.4:
        parts.append(f"Fed 降息路径清晰 ({fed_start:.1f}%→{fed_end:.1f}%)")
    elif fed_end < fed_start:
        parts.append(f"Fed 缓慢降息 ({fed_start:.1f}%→{fed_end:.1f}%)")
    else:
        parts.append("Fed 按兵不动")
    
    # 市场方向
    sp_start = initial.get("us_sp500", 6000)
    sp_end = final_state["sp500"]
    sp_chg = (sp_end - sp_start) / sp_start * 100
    if sp_chg > 5:
        parts.append(f"股市继续上行 (+{sp_chg:.0f}%)")
    elif sp_chg > 0:
        parts.append(f"股市温和上涨 (+{sp_chg:.0f}%)")
    else:
        parts.append(f"股市回落 ({sp_chg:.0f}%)")
    
    # 关键风险
    if final_state["reserve_share"] < 56:
        parts.append("去美元化速度加快⚠️")
    if final_state["china_pmi"] < 50:
        parts.append("中国经济增长承压")
    if final_state["vix"] > 28:
        parts.append("VIX持续高位")
    
    return " | ".join(parts)


# ═══════════════════════════════════════════════════════
#  博弈历史追踪
# ═══════════════════════════════════════════════════════

def save_game_snapshot(indicators: dict):
    """保存当前博弈快照到数据库。"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            date TEXT,
            player_id TEXT,
            status TEXT,
            bias TEXT,
            tension REAL,
            PRIMARY KEY (date, player_id)
        )
    """)
    today = date.today().isoformat()
    
    # 复用 V1 的 analyze 获取各玩家紧张度
    from engine.game_theory import analyze as v1_analyze
    players = v1_analyze()
    
    player_map = {
        "fed": "美联储", "china_gov": "中国政府", "markets": "全球市场",
        "china_markets": "中国资本市场", "eu": "欧盟/ECB", "commodity_producers": "资源出口国",
    }
    
    for pid, name in player_map.items():
        player = next((p for p in players if p["player"] == name), None)
        if player:
            tension = 0.1  # default
            status = player["status"]
            bias = player["bias"]
            if "高压" in status:
                tension = 0.5
            elif "承压" in status:
                tension = 0.25
            
            c.execute("""
                INSERT OR REPLACE INTO game_history (date, player_id, status, bias, tension)
                VALUES (?, ?, ?, ?, ?)
            """, (today, pid, status, bias, tension))
    
    conn.commit()
    conn.close()


def get_game_history(player_id: str = None, days: int = 7) -> list[dict]:
    """获取博弈历史。"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            date TEXT,
            player_id TEXT,
            status TEXT,
            bias TEXT,
            tension REAL,
            PRIMARY KEY (date, player_id)
        )
    """)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    
    if player_id:
        c.execute(
            "SELECT date, status, bias, tension FROM game_history WHERE player_id=? AND date>=? ORDER BY date",
            (player_id, cutoff)
        )
    else:
        c.execute(
            "SELECT date, player_id, status, bias, tension FROM game_history WHERE date>=? ORDER BY date",
            (cutoff,)
        )
    
    rows = c.fetchall()
    conn.close()
    
    if player_id:
        return [{"date": r[0], "status": r[1], "bias": r[2], "tension": r[3]} for r in rows]
    else:
        return [{"date": r[0], "player": r[1], "status": r[2], "bias": r[3], "tension": r[4]} for r in rows]


# ═══════════════════════════════════════════════════════
#  主分析函数
# ═══════════════════════════════════════════════════════

def analyze_v2() -> dict:
    """V2 博弈分析 — 包含动态博弈树。"""
    snap = get_snapshot()
    indicators = {}
    for k in snap:
        val = snap[k].get("value")
        if val is not None:
            indicators[k] = val
    
    # 1. V1 静态分析（各方状态）
    from engine.game_theory import analyze as v1_analyze, get_net_effects
    players = v1_analyze()
    net_effects = get_net_effects()
    
    # 2. 动态博弈树
    tree = simulate_game_tree(indicators, depth=3)
    
    # 3. 保存快照
    save_game_snapshot(indicators)
    
    # 4. 历史
    history = get_game_history(days=7)
    
    return {
        "date": date.today().isoformat(),
        "players": players,
        "net_effects": net_effects,
        "game_tree": tree,
        "history": history,
    }


# ═══════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tree-only", action="store_true", help="只显示博弈树")
    args = parser.parse_args()
    
    result = analyze_v2()
    
    if args.json:
        output = {k: v for k, v in result.items() if k != "game_tree"}
        output["game_tree_rounds"] = result["game_tree"]["rounds"]
        output["game_tree_trajectory"] = result["game_tree"]["net_trajectory"]
        output["terminal_scenarios"] = result["game_tree"]["terminal_scenarios"]
        print(json.dumps(output, ensure_ascii=False, indent=2))
    
    elif args.tree_only:
        tree = result["game_tree"]
        print(f"\n🎯 动态博弈树 — 3步前瞻模拟")
        print(f"  最终轨迹: {tree['net_trajectory']}")
        
        for r in tree["rounds"]:
            print(f"\n  ═══ 第{r['round']}轮 ═══")
            for player, move in r["moves"].items():
                name = PLAYERS.get(player, {}).get("name", player)
                impact = r["impacts"].get(player, "")
                print(f"  {name}: {move}")
                if impact:
                    print(f"    → {impact}")
            print(f"  📊 状态: SP500={r['state_snapshot']['SP500']} "
                  f"VIX={r['state_snapshot']['VIX']} "
                  f"黄金={r['state_snapshot']['黄金']}")
        
        print(f"\n  ═══ 终局场景 ═══")
        for s in tree["terminal_scenarios"]:
            print(f"  {s['name']} P={s['probability']:.0%}: {s['description']}")
    
    else:
        # 完整报告
        print(f"\n🎯 多方博弈分析 V2 — {result['date']}")
        
        # 各方状态
        print(f"\n  📋 参与方状态:")
        for p in result["players"]:
            print(f"  {p['status']} {p['player']}: {p['bias']}")
        
        # 博弈树摘要
        tree = result["game_tree"]
        print(f"\n  🌳 博弈树 (3步前瞻):")
        for r in tree["rounds"]:
            moves_str = " → ".join(f"{PLAYERS.get(k,{}).get('name',k)[:4]}:{v[:6]}" for k, v in r["moves"].items())
            print(f"    第{r['round']}轮: {moves_str}")
        print(f"    轨迹: {tree['net_trajectory']}")
        
        print(f"\n  🎲 终局场景:")
        for s in tree["terminal_scenarios"]:
            print(f"  {s['name']} P={s['probability']:.0%}: {s['description']}")
        
        # 净效应
        print(f"\n  ⚖️ 净效应:")
        for e in result["net_effects"]:
            print(f"  {e}")
