"""叙事分析引擎 V2 — 数据驱动的媒体情绪 + 转折点检测。

V2 新增（P0）：
1. 中文财经媒体情绪指数 — 爬取新浪财经/东方财富头条，计算牛熊比
2. 叙事转折点检测 — 共识太强时的"反指"信号
3. 叙事 vs 数据背离度 — 市场在讲一个故事，但数据在讲另一个
4. 历史情绪存档 — 存储多天情绪，追踪趋势变化

核心理念：Dalio 视角 6 —— "叙事驱动资金流，资金流驱动价格，价格验证叙事"
最危险的时刻：当所有人都相信一个叙事时，往往就是反转的前夜。
"""

import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from collections import Counter

import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.storage import get_snapshot, DB_PATH

# ═══════════════════════════════════════════════════════
#  中文财经情绪词典
# ═══════════════════════════════════════════════════════

BULLISH_WORDS = [
    # 直接看涨
    "暴涨", "大涨", "飙升", "新高", "牛市", "反弹", "突破", "利好",
    "强劲", "超预期", "大幅增长", "强势", "翻红", "普涨", "放量上涨",
    "资金涌入", "加仓", "抄底", "看多", "信心恢复", "企稳回升",
    "降息预期", "宽松", "刺激", "复苏", "回暖",
    # AI 叙事特有关键词
    "AI革命", "人工智能", "算力", "大模型", "科技股领涨", "降息周期",
    "软着陆", "金发女孩", "生产率提升",
]

BEARISH_WORDS = [
    # 直接看跌
    "暴跌", "大跌", "崩盘", "新低", "熊市", "跳水", "破位", "利空",
    "衰退", "低于预期", "大幅下滑", "走弱", "翻绿", "普跌", "放量下跌",
    "资金出逃", "减仓", "看空", "信心不足", "承压",
    "加息预期", "紧缩", "危机", "恶化",
    # 风险叙事特有关键词
    "贸易战", "关税", "脱钩", "制裁", "地缘风险", "战争",
    "滞胀", "硬着陆", "泡沫", "过度投机", "估值过高",
    "债务危机", "违约", "去美元化加速", "美元信用",
]

VOLATILITY_WORDS = [
    "震荡", "波动", "分化", "轮动", "不确定性", "观望",
    "纠结", "反复", "拉锯", "多空博弈", "方向不明",
]

# ═══════════════════════════════════════════════════════
#  新闻源配置
# ═══════════════════════════════════════════════════════

NEWS_SOURCES = [
    {
        "name": "新浪财经-宏观",
        "url": "https://finance.sina.com.cn/mac",
        "encoding": "utf-8",
        "headline_pattern": r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        "filter": lambda t: len(t) > 10 and any(w in t for w in ["经济","市场","政策","A股","美股","央行","利率","通胀","GDP","PMI","CPI","就业"]),
    },
    {
        "name": "东方财富-要闻",
        "url": "https://finance.eastmoney.com/a/czqyw.html",
        "encoding": "utf-8",
        "headline_pattern": r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        "filter": lambda t: len(t) > 10,
    },
    {
        "name": "新浪财经-国际",
        "url": "https://finance.sina.com.cn/worldmac",
        "encoding": "utf-8",
        "headline_pattern": r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        "filter": lambda t: len(t) > 10 and any(w in t for w in ["美国","美联储","美元","美股","欧洲","日本","黄金","石油"]),
    },
]


def fetch_headlines(source: dict, timeout: int = 15) -> list[str]:
    """爬取单个新闻源的头条标题。"""
    try:
        req = urllib.request.Request(
            source["url"],
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode(source.get("encoding", "utf-8"), errors="ignore")
        
        # 提取标题
        matches = re.findall(source["headline_pattern"], html, re.DOTALL)
        headlines = []
        for href, text in matches:
            # 清理 HTML 标签
            clean = re.sub(r'<[^>]+>', '', text).strip()
            # 清理空白
            clean = re.sub(r'\s+', ' ', clean)
            if source.get("filter", lambda x: True)(clean):
                headlines.append(clean)
        
        return headlines[:50]  # 最多50条
    except Exception as e:
        print(f"  ⚠️ {source['name']} 抓取失败: {e}")
        return []


def analyze_sentiment(headlines: list[str]) -> dict:
    """对头条列表做情绪分析。"""
    total = len(headlines)
    if total == 0:
        return {"bullish": 0, "bearish": 0, "volatile": 0, "neutral": 0,
                "total": 0, "bull_ratio": 0.5, "sentiment_score": 0,
                "top_bullish": [], "top_bearish": [], "top_volatile": []}
    
    bullish, bearish, volatile, neutral = 0, 0, 0, 0
    top_bullish, top_bearish, top_volatile = [], [], []
    
    for h in headlines:
        b_score = sum(1 for w in BULLISH_WORDS if w in h)
        be_score = sum(1 for w in BEARISH_WORDS if w in h)
        v_score = sum(1 for w in VOLATILITY_WORDS if w in h)
        
        if b_score > be_score and b_score > v_score:
            bullish += 1
            if len(top_bullish) < 5:
                top_bullish.append(h[:60])
        elif be_score > b_score and be_score > v_score:
            bearish += 1
            if len(top_bearish) < 5:
                top_bearish.append(h[:60])
        elif v_score > b_score and v_score > be_score:
            volatile += 1
            if len(top_volatile) < 5:
                top_volatile.append(h[:60])
        else:
            neutral += 1
    
    # bull_ratio: 有效情绪中的看多占比（排除中性）
    effective = bullish + bearish
    bull_ratio = bullish / effective if effective > 0 else 0.5
    # 中性率
    neutral_ratio = neutral / total if total > 0 else 0
    # 情绪分数: -1(恐慌) ~ +1(狂热) — 有效情绪加权
    sentiment_score = (bullish - bearish) / effective if effective > 0 else 0
    
    return {
        "bullish": bullish, "bearish": bearish, "volatile": volatile,
        "neutral": neutral, "total": total,
        "bull_ratio": round(bull_ratio, 2),
        "neutral_ratio": round(neutral_ratio, 2),
        "sentiment_score": round(sentiment_score, 2),
        "top_bullish": top_bullish,
        "top_bearish": top_bearish,
        "top_volatile": top_volatile,
    }


def detect_tipping_point(current: dict, history: list) -> dict:
    """检测叙事转折点。
    
    关键信号：
    1. 牛熊比极端（>0.75 或 <0.25）→ 共识过度
    2. 情绪连续3天单向 → 动量衰竭风险
    3. 牛熊比发生 >30% 的突变 → 叙事切换
    """
    signals = []
    risk_level = "normal"
    
    bull_ratio = current.get("bull_ratio", 0.5)
    sentiment = current.get("sentiment_score", 0)
    
    # 信号1：极端共识
    if bull_ratio >= 0.80:
        signals.append(f"🚨 极端看多共识 (牛熊比={bull_ratio}) — 「所有人都在船上」反转风险极高")
        risk_level = "critical"
    elif bull_ratio >= 0.70:
        signals.append(f"⚠️ 高度看多共识 (牛熊比={bull_ratio}) — 关注反转信号")
        if risk_level == "normal":
            risk_level = "elevated"
    elif bull_ratio <= 0.20:
        signals.append(f"🚨 极端看空共识 (牛熊比={bull_ratio}) — 恐慌见底信号")
        risk_level = "critical"
    elif bull_ratio <= 0.30:
        signals.append(f"⚠️ 高度看空共识 (牛熊比={bull_ratio}) — 关注反弹信号")
        if risk_level == "normal":
            risk_level = "elevated"
    
    # 信号2：连续单向
    if history and len(history) >= 3:
        last_3 = history[-3:]
        all_bull = all(h.get("bull_ratio", 0.5) > 0.6 for h in last_3)
        all_bear = all(h.get("bull_ratio", 0.5) < 0.4 for h in last_3)
        if all_bull:
            signals.append("⚠️ 连续3天看多 — 动量可能衰竭")
        if all_bear:
            signals.append("⚠️ 连续3天看空 — 情绪可能触底")
    
    # 信号3：突变
    if history and len(history) >= 1:
        prev = history[-1]
        prev_ratio = prev.get("bull_ratio", 0.5)
        delta = abs(bull_ratio - prev_ratio)
        if delta >= 0.30:
            direction = "转多" if bull_ratio > prev_ratio else "转空"
            signals.append(f"🔔 叙事突变 (变化={delta:.0%}) — 市场正在{direction}")
            risk_level = "elevated"
    
    return {
        "tipping_point_risk": risk_level,
        "signals": signals,
        "is_extreme": risk_level in ("critical", "elevated"),
    }


def measure_narrative_data_divergence(sentiment: dict, snapshot: dict) -> dict:
    """衡量叙事与数据的背离度。
    
    场景举例：
    - 媒体极度看多，但 PMI < 45 → 危险的乐观
    - 媒体极度看空，但 PMI > 55 → 过度恐慌
    
    Dalio 称之为「认知失调」—— 市场在讲一个故事，现实在讲另一个。
    """
    divergences = []
    divergence_score = 0
    
    bull_ratio = sentiment.get("bull_ratio", 0.5)
    
    # 取关键宏观数据
    us_pmi = None
    china_pmi = None
    vix = None
    
    pmi_data = snapshot.get("us_ism_pmi", {}) or snapshot.get("us_pmi", {})
    if pmi_data and pmi_data.get("value") is not None:
        us_pmi = pmi_data["value"]
    
    cn_pmi = snapshot.get("china_pmi", {})
    if cn_pmi and cn_pmi.get("value") is not None:
        china_pmi = cn_pmi["value"]
    
    vix_data = snapshot.get("us_vixy", {})
    if vix_data and vix_data.get("value") is not None:
        vix = vix_data["value"]
    
    # 背离1：看多但经济在收缩
    if bull_ratio > 0.60 and us_pmi is not None and us_pmi < 45:
        divergences.append(f"⚠️ 媒体乐观(bull={bull_ratio}) vs PMI={us_pmi}收缩 — 危险的乐观")
        divergence_score += 30
    elif bull_ratio < 0.40 and us_pmi is not None and us_pmi > 55:
        divergences.append(f"⚠️ 媒体悲观(bull={bull_ratio}) vs PMI={us_pmi}扩张 — 过度恐慌")
        divergence_score += 30
    
    # 背离2：看多但波动率飙升
    if bull_ratio > 0.55 and vix is not None and vix > 25:
        divergences.append(f"⚠️ 媒体乐观(bull={bull_ratio}) vs VIX={vix}高位 — 市场在用脚投票")
        divergence_score += 25
    elif bull_ratio < 0.45 and vix is not None and vix < 15:
        divergences.append(f"⚠️ 媒体悲观(bull={bull_ratio}) vs VIX={vix}低位 — 恐慌可能过度")
        divergence_score += 25
    
    # 背离3：中国看多但数据弱
    if bull_ratio > 0.55 and china_pmi is not None and china_pmi < 48:
        divergences.append(f"⚠️ 中国数据走弱(PMI={china_pmi}) vs 媒体乐观 — 政策预期透支")
        divergence_score += 20
    
    level = "normal"
    if divergence_score >= 50:
        level = "critical"
    elif divergence_score >= 30:
        level = "elevated"
    
    return {
        "divergences": divergences,
        "divergence_score": divergence_score,
        "level": level,
    }


def save_sentiment_record(record: dict):
    """保存情绪记录到数据库。"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_history (
            date TEXT PRIMARY KEY,
            sentiment_score REAL,
            bull_ratio REAL,
            total_headlines INTEGER,
            tipping_risk TEXT,
            divergence_score INTEGER,
            full_data TEXT
        )
    """)
    c.execute("""
        INSERT OR REPLACE INTO sentiment_history 
        (date, sentiment_score, bull_ratio, total_headlines, tipping_risk, divergence_score, full_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        record["date"],
        record.get("sentiment_score", 0),
        record.get("bull_ratio", 0.5),
        record.get("total_headlines", 0),
        record.get("tipping_risk", "normal"),
        record.get("divergence_score", 0),
        json.dumps(record, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def get_sentiment_history(days: int = 7) -> list:
    """获取最近N天情绪历史。"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_history (
            date TEXT PRIMARY KEY,
            sentiment_score REAL,
            bull_ratio REAL,
            total_headlines INTEGER,
            tipping_risk TEXT,
            divergence_score INTEGER,
            full_data TEXT
        )
    """)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    c.execute(
        "SELECT date, sentiment_score, bull_ratio, total_headlines, tipping_risk, divergence_score FROM sentiment_history WHERE date >= ? ORDER BY date",
        (cutoff,)
    )
    rows = c.fetchall()
    conn.close()
    return [
        {
            "date": r[0], "sentiment_score": r[1], "bull_ratio": r[2],
            "total_headlines": r[3], "tipping_risk": r[4], "divergence_score": r[5],
        }
        for r in rows
    ]


# ═══════════════════════════════════════════════════════
#  V2 叙事主函数 — crawler + 存量叙事整合
# ═══════════════════════════════════════════════════════

def run_narrative_v2(skip_crawl: bool = False) -> dict:
    """运行 V2 叙事分析。
    
    Args:
        skip_crawl: True 时跳过爬虫（网络不可用时）
    
    Returns:
        {
            "media_sentiment": {...},      # 媒体情绪分析
            "tipping_point": {...},        # 转折点检测
            "divergence": {...},           # 背离分析
            "narrative_themes": [...],     # 存量叙事主题 (V1)
            "history": [...],              # 近7天情绪历史
            "summary": str,                # 一句话总结
        }
    """
    snapshot = get_snapshot()
    today = date.today().isoformat()
    
    # 1. 爬取 + 分析媒体情绪
    if not skip_crawl:
        all_headlines = []
        for source in NEWS_SOURCES:
            headlines = fetch_headlines(source)
            all_headlines.extend(headlines)
            time.sleep(0.5)  # 礼貌爬取
        
        # 去重
        seen = set()
        unique_headlines = []
        for h in all_headlines:
            short = h[:30]
            if short not in seen:
                seen.add(short)
                unique_headlines.append(h)
        
        media_sentiment = analyze_sentiment(unique_headlines)
    else:
        # 离线模式：使用假数据或上次记录
        history = get_sentiment_history(1)
        if history:
            last = history[-1]
            media_sentiment = {
                "bullish": 0, "bearish": 0, "volatile": 0, "neutral": 0,
                "total": last["total_headlines"],
                "bull_ratio": last["bull_ratio"],
                "sentiment_score": last["sentiment_score"],
                "top_bullish": [], "top_bearish": [], "top_volatile": [],
                "_offline": True,
            }
        else:
            media_sentiment = {
                "bullish": 0, "bearish": 0, "volatile": 0, "neutral": 0,
                "total": 0, "bull_ratio": 0.5, "sentiment_score": 0,
                "top_bullish": [], "top_bearish": [], "top_volatile": [],
                "_offline": True,
            }
    
    # 2. 转折点检测
    sentiment_history = get_sentiment_history(7)
    tipping = detect_tipping_point(media_sentiment, sentiment_history)
    
    # 3. 叙事-数据背离
    divergence = measure_narrative_data_divergence(media_sentiment, snapshot)
    
    # 4. 保存今日记录
    record = {
        "date": today,
        "sentiment_score": media_sentiment.get("sentiment_score", 0),
        "bull_ratio": media_sentiment.get("bull_ratio", 0.5),
        "total_headlines": media_sentiment.get("total", 0),
        "tipping_risk": tipping.get("tipping_point_risk", "normal"),
        "divergence_score": divergence.get("divergence_score", 0),
        "bullish_count": media_sentiment.get("bullish", 0),
        "bearish_count": media_sentiment.get("bearish", 0),
    }
    if not skip_crawl and not media_sentiment.get("_offline"):
        save_sentiment_record(record)
    
    # 5. 汇总
    summary_parts = []
    if tipping.get("is_extreme"):
        summary_parts.append(f"🚨 情绪极端 (牛熊比={media_sentiment['bull_ratio']})")
    if divergence.get("level") != "normal":
        summary_parts.append(f"⚠️ 叙事-数据背离 (得分={divergence['divergence_score']})")
    if not summary_parts:
        score = media_sentiment.get("sentiment_score", 0)
        if score > 0.2:
            summary_parts.append("🟢 媒体偏向乐观")
        elif score < -0.2:
            summary_parts.append("🔴 媒体偏向悲观")
        else:
            summary_parts.append("🟡 媒体情绪中性")
    
    return {
        "date": today,
        "media_sentiment": media_sentiment,
        "tipping_point": tipping,
        "divergence": divergence,
        "history": sentiment_history,
        "summary": " | ".join(summary_parts),
    }


# ═══════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-crawl", action="store_true", help="跳过新闻爬取")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    
    result = run_narrative_v2(skip_crawl=args.skip_crawl)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        ms = result["media_sentiment"]
        print(f"\n📰 媒体情绪分析 — {result['date']}")
        print(f"  头条抓取: {ms['total']} 条")
        print(f"  看多: {ms['bullish']} | 看空: {ms['bearish']} | 震荡: {ms['volatile']} | 中性: {ms['neutral']}")
        print(f"  牛熊比: {ms['bull_ratio']} | 情绪分: {ms['sentiment_score']} (-1恐 ~ +1贪)")
        if ms.get("top_bullish"):
            print(f"  📈 看多头条: {ms['top_bullish'][0]}")
        if ms.get("top_bearish"):
            print(f"  📉 看空头条: {ms['top_bearish'][0]}")
        
        tp = result["tipping_point"]
        print(f"\n🔔 转折点检测: {tp['tipping_point_risk'].upper()}")
        for sig in tp["signals"]:
            print(f"  {sig}")
        
        dv = result["divergence"]
        print(f"\n📏 背离分析: {dv['level'].upper()} (得分={dv['divergence_score']})")
        for d in dv["divergences"]:
            print(f"  {d}")
        
        print(f"\n📊 总结: {result['summary']}")
        
        if result["history"]:
            print(f"\n📈 近7天情绪趋势:")
            for h in result["history"]:
                bar = "🟢" if h["bull_ratio"] > 0.6 else ("🔴" if h["bull_ratio"] < 0.4 else "🟡")
                print(f"  {h['date']} {bar} 牛熊比={h['bull_ratio']} 风险={h['tipping_risk']}")
