"""反向压力测试引擎 V2 — 公式化概率版。

V2 新增（P0）：
1. 前置条件独立概率 — sigmoid 函数将数据值映射到 [0, 1]
2. 加权综合概率 — Dalio 公式 P_total = f(P1^w1, P2^w2, ...)
3. 历史概率追踪 — 保存每次计算，追踪趋势
4. 场景触发告警 — 当综合概率突破阈值时标记

核心理念：Dalio 视角 4 ——
"从极端场景出发，回溯触发条件，监控前置信号，更新概率"
"""

import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, DB_PATH

# 复用现有场景定义
from engine.stress_test import SCENARIOS


# ═══════════════════════════════════════════════════════
#  概率映射函数 — sigmoid 将数据值转为独立概率
# ═══════════════════════════════════════════════════════

def sigmoid_prob(value: float, threshold: float, direction: str = ">",
                 steepness: float = 1.0, floor: float = 0.05,
                 ceiling: float = 0.98) -> float:
    """将数据值映射为前置条件激活概率。
    
    Args:
        value: 当前数据值
        threshold: 触发阈值
        direction: ">" 表示超过阈值触发，">>" 表示远远超过触发概率
        steepness: 坡度（越小越平缓，越大越陡峭）
        floor: 最低概率下限
        ceiling: 最高概率上限
    
    math:
        P(value) = floor + (ceiling - floor) * sigmoid(steepness * (value - threshold) / |threshold|)
        其中 sigmoid(x) = 1 / (1 + e^(-x))
        
        当 direction="<" 时，取反：P(value) = 1 - P(value)
    
    举例：
        debt_gdp=135% vs threshold=130%, steepness=5:
        sigmoid(5*5/130) = sigmoid(0.192) ≈ 0.548 → P ≈ 0.56
    """
    if threshold == 0:
        return floor
    
    # 归一化距离
    normalized_distance = steepness * (value - threshold) / abs(threshold)
    
    if direction == ">":
        raw = 1.0 / (1.0 + math.exp(-normalized_distance))
    elif direction == "<<":
        # << 表示远远低于触发（value低于threshold越多概率越高）
        raw = 1.0 / (1.0 + math.exp(normalized_distance))
    elif direction == "<":
        raw = 1.0 / (1.0 + math.exp(normalized_distance))
    else:
        raw = 0.5
    
    return floor + (ceiling - floor) * raw


def calc_precondition_prob(key: str, op: str, threshold: float,
                           snapshot: dict) -> tuple[float, Optional[float], str]:
    """计算单个前置条件的激活概率。
    
    Returns:
        (probability, actual_value, status)
    """
    # 查找数据
    value = None
    # 尝试直接匹配
    if key in snapshot and isinstance(snapshot[key], dict):
        value = snapshot[key].get("value")
    else:
        # 在嵌套字段中搜索
        for k, v in snapshot.items():
            if isinstance(v, dict) and key in k:
                value = v.get("value")
                break
            elif isinstance(v, (int, float)) and key in k.lower():
                value = v
                break
    
    if value is None:
        return (0.0, None, "⚠️ 数据缺失")
    
    direction = op  # ">", "<", ">>", "<<"
    prob = sigmoid_prob(float(value), float(threshold), direction=direction)
    
    status = "🟢" if prob < 0.3 else ("🟡" if prob < 0.6 else ("🔴" if prob < 0.85 else "💀"))
    return (prob, float(value), f"{status} P={prob:.0%} (={value} {op} {threshold})")


# ═══════════════════════════════════════════════════════
#  加权综合概率 — Dalio 的乘法加权公式
# ═══════════════════════════════════════════════════════

def composite_probability(probs: list[float], weights: list[float] = None) -> dict:
    """加权综合概率。
    
    Dalio 的逻辑（来自深度研究）：
    触发条件 P1, P2, P3, P4 各自独立激活 → 综合概率 ≈ 乘法加权
    
    公式：
    P_total = (P1^w1 × P2^w2 × ...)^(1/Σw) × 缩放因子
    
    为什么用乘法而非加法？
    - 美元崩盘需要政治极化↗ AND 债务过高↗ AND 信心丧失↗
    - 如果任何一个条件不满足(0%)，综合概率应为 0%
    - 乘法天然捕捉"AND"关系
    
    缩放因子确保：当所有 Pi=0.5 时，P_total≈0.5（而不是趋近 0）
    """
    if not probs:
        return {"probability": 0.0, "method": "none"}
    
    n = len(probs)
    if weights is None:
        weights = [1.0] * n
    
    # 归一化权重
    w_sum = sum(weights)
    if w_sum == 0:
        return {"probability": 0.0, "method": "no_weights"}
    norm_weights = [w / w_sum for w in weights]
    
    # 乘法加权
    product = 1.0
    for p, w in zip(probs, norm_weights):
        # 处理边界：p=0 时取极小值避免 total=0
        p_safe = max(p, 0.001)
        product *= p_safe ** w
    
    # 缩放：使得全 0.5 时 total≈0.5
    # 当 Pi=0.5, product = 0.5^(1)=0.5，恰好
    # 但加权后 product = Π 0.5^wi，可能偏离
    # 缩放因子 = 0.5 / (0.5 ^ 平均权重)
    avg_weight = sum(norm_weights) / n
    scale = 0.5 / (0.5 ** avg_weight) if avg_weight > 0 else 1.0
    
    p_total = min(product * scale, 0.999)
    
    # 确保 floor
    p_total = max(p_total, 0.001)
    
    return {
        "probability": round(p_total, 4),
        "method": f"multiply_weighted(n={n}, Σw={w_sum})",
        "scale_factor": round(scale, 3),
        "individual": [round(p, 4) for p in probs],
        "weights": [round(w, 2) for w in norm_weights],
    }


# ═══════════════════════════════════════════════════════
#  场景概率综合计算
# ═══════════════════════════════════════════════════════

def evaluate_all_scenarios(snapshot: dict = None) -> list[dict]:
    """对所有28个场景计算公式化概率。
    
    Returns:
        按概率降序排列的场景列表
    """
    if snapshot is None:
        snapshot = get_snapshot()
    
    results = []
    
    for scene_id, scene in SCENARIOS.items():
        preconditions = scene.get("preconditions", [])
        
        # 计算每个前置条件的独立概率
        cond_results = []
        probs = []
        
        for i, (key, op, threshold) in enumerate(preconditions):
            prob, val, status = calc_precondition_prob(key, op, threshold, snapshot)
            cond_results.append({
                "key": key,
                "op": op,
                "threshold": threshold,
                "value": val,
                "probability": round(prob, 4),
                "status": status,
            })
            probs.append(prob)
        
        # 加权综合概率
        # 默认等权重，第一个条件权重略高（通常是最核心的）
        weights = [1.5] + [1.0] * (len(probs) - 1) if len(probs) > 1 else [1.0]
        composite = composite_probability(probs, weights)
        
        # 风险等级
        p = composite["probability"]
        if p > 0.65:
            risk_level = "💀 extreme"
        elif p > 0.40:
            risk_level = "🔴 high"
        elif p > 0.20:
            risk_level = "🟡 elevated"
        elif p > 0.10:
            risk_level = "🟢 moderate"
        else:
            risk_level = "⚪ low"
        
        results.append({
            "id": scene_id,
            "label": scene["label"],
            "severity": scene.get("severity", "unknown"),
            "category": scene.get("category", "general"),
            "description": scene.get("description", ""),
            "probability": round(p, 4),
            "risk_level": risk_level,
            "preconditions": cond_results,
            "composite": composite,
            "assumed_impact": scene.get("assumed_impact", {}),
        })
    
    # 按概率降序
    results.sort(key=lambda r: r["probability"], reverse=True)
    return results


def get_top_risks(results: list[dict], top_n: int = 8) -> list[dict]:
    """获取概率最高的 N 个场景。"""
    return [r for r in results if r["probability"] > 0.05][:top_n]


def get_active_alerts(results: list[dict], threshold: float = 0.30) -> list[dict]:
    """获取需要关注的场景（概率超过阈值）。"""
    return [r for r in results if r["probability"] >= threshold]


def save_probability_snapshot(results: list[dict]):
    """保存概率快照到数据库。"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS stress_test_history (
            date TEXT,
            scenario_id TEXT,
            probability REAL,
            risk_level TEXT,
            PRIMARY KEY (date, scenario_id)
        )
    """)
    today = date.today().isoformat()
    for r in results:
        c.execute("""
            INSERT OR REPLACE INTO stress_test_history (date, scenario_id, probability, risk_level)
            VALUES (?, ?, ?, ?)
        """, (today, r["id"], r["probability"], r["risk_level"]))
    conn.commit()
    conn.close()


def get_probability_history(scenario_id: str, days: int = 7) -> list[dict]:
    """获取某场景的历史概率趋势。"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS stress_test_history (
            date TEXT,
            scenario_id TEXT,
            probability REAL,
            risk_level TEXT,
            PRIMARY KEY (date, scenario_id)
        )
    """)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    c.execute(
        "SELECT date, probability, risk_level FROM stress_test_history WHERE scenario_id=? AND date>=? ORDER BY date",
        (scenario_id, cutoff)
    )
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "probability": r[1], "risk_level": r[2]} for r in rows]


# ═══════════════════════════════════════════════════════
#  汇总函数
# ═══════════════════════════════════════════════════════

def run_stress_test_v2() -> dict:
    """运行 V2 压力测试，返回完整结果。"""
    snapshot = get_snapshot()
    results = evaluate_all_scenarios(snapshot)
    save_probability_snapshot(results)
    
    top = get_top_risks(results, 10)
    alerts = get_active_alerts(results, 0.25)
    
    # 统计
    extreme_count = sum(1 for r in results if r["probability"] > 0.65)
    high_count = sum(1 for r in results if 0.40 < r["probability"] <= 0.65)
    elevated_count = sum(1 for r in results if 0.20 < r["probability"] <= 0.40)
    
    summary = (
        f"28场景评估完成 | "
        f"💀={extreme_count} 🔴={high_count} 🟡={elevated_count} | "
        f"需关注={len(alerts)}个场景"
    )
    
    return {
        "date": date.today().isoformat(),
        "total_scenarios": len(results),
        "summary": summary,
        "extreme_count": extreme_count,
        "high_count": high_count,
        "elevated_count": elevated_count,
        "alert_count": len(alerts),
        "top_risks": top,
        "alerts": alerts,
        "all_results": results,
    }


# ═══════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--top", type=int, default=10, help="显示 TOP N")
    parser.add_argument("--detail", type=str, help="查看指定场景的详细概率分解")
    args = parser.parse_args()
    
    result = run_stress_test_v2()
    
    if args.detail:
        # 显示单个场景的详细概率分解
        scene = next((r for r in result["all_results"] if r["id"] == args.detail), None)
        if scene:
            print(f"\n🔍 {scene['label']} — 概率分解")
            print(f"  综合概率: {scene['probability']:.1%} [{scene['risk_level']}]")
            print(f"  方法: {scene['composite']['method']}")
            print(f"  缩放因子: {scene['composite']['scale_factor']}")
            print(f"\n  前置条件:")
            for i, pc in enumerate(scene['preconditions']):
                w = scene['composite']['weights'][i]
                print(f"    {pc['key']} {pc['op']} {pc['threshold']} → "
                      f"P={pc['probability']:.1%} (实际={pc['value']}) 权重={w}")
            print(f"\n  假设影响:")
            for asset, impact in scene.get("assumed_impact", {}).items():
                print(f"    {asset}: {impact}")
        else:
            print(f"⚠️ 未找到场景: {args.detail}")
    
    elif args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    else:
        print(f"\n⚠️ 反向压力测试 V2 — {result['date']}")
        print(f"  {result['summary']}")
        print(f"\n  TOP {args.top} 风险场景 (公式化概率):")
        print(f"  {'─'*70}")
        for i, r in enumerate(result["all_results"][:args.top], 1):
            bar = "█" * int(r["probability"] * 20)
            cat = r.get("category", "").upper()
            print(f"  {i:2d}. [{r['risk_level'][:2]}] {r['label']:<18s} "
                  f"P={r['probability']:.1%} {bar}")
            # 显示最高概率的前置条件
            if r["preconditions"]:
                top_pc = max(r["preconditions"], key=lambda x: x["probability"])
                print(f"       └─ {top_pc['key']}={top_pc['value']} {top_pc['op']} {top_pc['threshold']} "
                      f"(P={top_pc['probability']:.0%})")
        
        if result["alerts"]:
            print(f"\n  🚨 需要关注的场景 (P > 25%):")
            for r in result["alerts"]:
                print(f"    [{r['risk_level'][:2]}] {r['label']} P={r['probability']:.1%}")
