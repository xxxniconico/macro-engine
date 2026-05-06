"""历史模板匹配引擎 — 余弦相似度比对当前宏观状态与历史经典时期。

基于 Dalio 框架：找到与当前最相似的历史时期，参考其演化路径。
"""

import sys
from pathlib import Path
from datetime import date, datetime

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, get_all_templates

# ═══════════════════════════════════════════════════════════════
# 特征定义: (名称, 快照键候选列表, min, max, 中位参考)
# 归一化到 [-1, 1]
# ═══════════════════════════════════════════════════════════════
FEATURES = [
    ("gdp_growth",      ["china_gdp_growth", "us_gdp_growth"],        -5,   12,  3.5),
    ("inflation",       ["china_cpi", "us_cpi"],                      -2,   12,  5.0),
    ("pmi",             ["china_pmi"],                                 40,   60, 50.0),
    ("debt_gdp",        ["china_debt_gdp", "us_debt_gdp"],           100,  400, 250.0),
    ("real_rate",       ["us_real_rate", "china_real_rate"],          -5,    8,  1.5),
    ("unemployment",    ["china_unemployment", "us_unemployment"],     3,   15,  9.0),
    ("equity_1y",       ["us_sp500", "china_sh_index"],              -50,   50,  0.0),
    ("gold_1y",         ["gold", "gold_1y_reference"],               -30,   50, 10.0),
    ("policy_rate",     ["us_fed_rate"],                               0,   15,  7.5),
    ("reserve_status",  ["usd_reserve_share"],                        40,   70, 55.0),
    ("polarization",    ["us_political_polarization"],                40,   90, 65.0),
    ("inequality",      ["us_wealth_gap"],                           0.30, 0.50, 0.40),
]

FEATURE_NAMES = [f[0] for f in FEATURES]


def normalize(value: float | None, min_val: float, max_val: float) -> float:
    """Min-max 归一化到 [-1, 1]。缺值返回 0（中性）。"""
    if value is None:
        return 0.0
    mid = (min_val + max_val) / 2.0
    half = (max_val - min_val) / 2.0
    if half == 0:
        return 0.0
    return float(np.clip((value - mid) / half, -1.0, 1.0))


def extract_features(snapshot: dict) -> tuple[np.ndarray, np.ndarray]:
    """从快照提取归一化特征向量 + 可用性掩码。

    Returns:
        vec:  shape (12,) float32, 归一化特征值
        mask: shape (12,) float32, 1=有数据, 0=缺失
    """
    vec = np.zeros(len(FEATURES), dtype=np.float32)
    mask = np.zeros(len(FEATURES), dtype=np.float32)

    for i, (name, keys, min_v, max_v, _mid) in enumerate(FEATURES):
        value = None
        for key in keys:
            entry = snapshot.get(key)
            if entry and entry.get("value") is not None:
                value = entry["value"]
                break

        # 特殊处理: gold_1y = (gold - gold_1y_reference) / gold_1y_reference * 100
        if name == "gold_1y":
            gold_now = snapshot.get("gold", {}).get("value")
            gold_ref = snapshot.get("gold_1y_reference", {}).get("value")
            if gold_now and gold_ref and gold_ref > 0:
                value = (gold_now - gold_ref) / gold_ref * 100
            else:
                value = None

        if value is not None:
            vec[i] = normalize(value, min_v, max_v)
            mask[i] = 1.0

    return vec, mask


def masked_cosine(a_vec, a_mask, b_vec, b_mask) -> float:
    """掩码余弦相似度：只在双方都有数据的维度上计算。

    双方都缺失的维度贡献 0，不参与归一化。
    """
    combined = a_mask * b_mask
    common = combined.sum()
    if common == 0:
        return 0.0

    a_m = a_vec * combined
    b_m = b_vec * combined

    norm_a = np.linalg.norm(a_m)
    norm_b = np.linalg.norm(b_m)

    if norm_a < 1e-8 or norm_b < 1e-8:
        return 0.0

    return float(np.dot(a_m, b_m) / (norm_a * norm_b))


def match(current_vec, current_mask, templates: list[dict]) -> list[dict]:
    """匹配当前向量 vs 所有历史模板，返回 Top 5。

    模板 vector 格式: {"values": [...], "mask": [...]}
    """
    results = []
    for t in templates:
        v = t["vector"]
        if isinstance(v, dict):
            raw_values = v.get("values", [])
            raw_mask = v.get("mask", [1]*len(FEATURES))
        else:
            raw_values = v
            raw_mask = t.get("mask", [1]*len(FEATURES))
        tv = np.array(raw_values, dtype=np.float32)
        tm = np.array(raw_mask, dtype=np.float32)
        sim = masked_cosine(current_vec, current_mask, tv, tm)
        overlap = int((current_mask * tm).sum())
        results.append({
            "name":        t["name"],
            "country":     t.get("country", ""),
            "period":      t.get("period", ""),
            "similarity":  round(sim, 4),
            "overlap":     overlap,
            "outcome":     t.get("outcome_summary", ""),
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:5]


def run_matcher(date_str: str = None) -> dict:
    """一键运行模板匹配。

    Returns:
        {
            "date": str,
            "available_features": int,
            "total_features": int,
            "current_features": list[float],
            "matches": list[dict]  # Top 5
        }
    """
    snap = get_snapshot(date_str)
    current_vec, current_mask = extract_features(snap)
    templates = get_all_templates()

    if not templates:
        return {
            "date": date_str or date.today().isoformat(),
            "available_features": int(current_mask.sum()),
            "total_features": len(FEATURES),
            "current_features": current_vec.tolist(),
            "matches": [],
            "message": "⚠️ 数据库无历史模板，请运行 data/manual/templates.py 播种"
        }

    matches = match(current_vec, current_mask, templates)

    return {
        "date": date_str or date.today().isoformat(),
        "available_features": int(current_mask.sum()),
        "total_features": len(FEATURES),
        "feature_names": FEATURE_NAMES,
        "current_features": current_vec.tolist(),
        "matches": matches,
    }


def format_report(result: dict) -> str:
    """格式化匹配结果为可读文本。"""
    lines = [
        "═" * 50,
        f"  历史模板匹配 — {result['date']}",
        f"  可用特征: {result['available_features']}/{result['total_features']}",
        "═" * 50,
        "",
    ]

    if result.get("message"):
        lines.append(result["message"])
        return "\n".join(lines)

    if not result["matches"]:
        lines.append("  (无匹配结果)")
        return "\n".join(lines)

    for i, m in enumerate(result["matches"], 1):
        sim_pct = m["similarity"] * 100
        bar = "▓" * int(sim_pct // 5) + "░" * (20 - int(sim_pct // 5))
        emoji = "🟢" if sim_pct > 70 else ("🟡" if sim_pct > 40 else "🔴")
        lines.append(f"  #{i} {emoji} {m['name']}")
        lines.append(f"      {m['country']} | {m['period']}")
        lines.append(f"      相似度: {sim_pct:.1f}% {bar}  (重叠 {m['overlap']} 维)")
        if m["outcome"]:
            lines.append(f"      结果: {m['outcome']}")
        lines.append("")

    return "\n".join(lines)


# ═════════ CLI ═════════

if __name__ == "__main__":
    r = run_matcher()
    print(format_report(r))
