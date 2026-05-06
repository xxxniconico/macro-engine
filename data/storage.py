"""SQLite 数据存储层 — 统一读写接口。

Schema:
  macro_indicators: 时序数据，一条记录 = 一个指标在一天的值
  historical_templates: 历史时期快照向量
  cycle_diagnoses: 周期诊断历史
"""

import sqlite3
import json
from datetime import date, datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "macro.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构。"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS macro_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_name TEXT NOT NULL,
            value REAL,
            date TEXT NOT NULL,
            source TEXT,
            confidence REAL DEFAULT 0.9,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(indicator_name, date, source)
        );

        CREATE TABLE IF NOT EXISTS historical_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            country TEXT,
            period TEXT,
            vector_json TEXT NOT NULL,
            outcome_summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cycle_diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            short_term_stage TEXT,
            short_term_confidence REAL,
            long_term_stage TEXT,
            long_term_confidence REAL,
            empire_stage TEXT,
            empire_confidence REAL,
            detail_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_indicators_name_date 
            ON macro_indicators(indicator_name, date);
        CREATE INDEX IF NOT EXISTS idx_diagnoses_date 
            ON cycle_diagnoses(date);
    """)
    conn.commit()
    conn.close()


def save_indicator(name: str, value: float, date_str: str, 
                   source: str = "unknown", confidence: float = 0.9):
    """保存一条宏观指标。自动 upsert（同一天同来源覆盖）。"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO macro_indicators (indicator_name, value, date, source, confidence)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(indicator_name, date, source) DO UPDATE SET
            value = excluded.value,
            confidence = excluded.confidence,
            created_at = datetime('now')
    """, (name, value, date_str, source, confidence))
    conn.commit()
    conn.close()


def get_latest(indicator_name: str) -> dict | None:
    """获取某个指标的最新值。"""
    conn = get_conn()
    row = conn.execute("""
        SELECT * FROM macro_indicators 
        WHERE indicator_name = ? 
        ORDER BY date DESC LIMIT 1
    """, (indicator_name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_series(indicator_name: str, limit: int = 60) -> list[dict]:
    """获取某个指标的时间序列。"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT date, value FROM macro_indicators 
        WHERE indicator_name = ? 
        ORDER BY date DESC LIMIT ?
    """, (indicator_name, limit)).fetchall()
    conn.close()
    return [{"date": r["date"], "value": r["value"]} for r in reversed(rows)]


def get_snapshot(date_str: str = None) -> dict:
    """获取某一天所有指标的快照，返回 {indicator_name: value}。"""
    if date_str is None:
        date_str = date.today().isoformat()
    
    conn = get_conn()
    # 对每个指标取最近不超过 date_str 的值
    rows = conn.execute("""
        SELECT indicator_name, value, confidence, MAX(date) as max_date
        FROM macro_indicators
        WHERE date <= ?
        GROUP BY indicator_name
    """, (date_str,)).fetchall()
    conn.close()
    
    return {r["indicator_name"]: {
        "value": r["value"],
        "confidence": r["confidence"],
        "date": r["max_date"]
    } for r in rows}


def save_template(name: str, country: str, period: str, 
                  vector: dict, outcome: str = ""):
    """保存历史模板。"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO historical_templates (name, country, period, vector_json, outcome_summary)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            vector_json = excluded.vector_json,
            outcome_summary = excluded.outcome_summary
    """, (name, country, period, json.dumps(vector, ensure_ascii=False), outcome))
    conn.commit()
    conn.close()


def get_all_templates() -> list[dict]:
    """获取所有历史模板。"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM historical_templates").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["vector"] = json.loads(d["vector_json"])
        result.append(d)
    return result


def save_diagnosis(short_stage: str, short_conf: float,
                   long_stage: str, long_conf: float,
                   empire_stage: str, empire_conf: float,
                   detail: dict = None):
    """保存一次周期诊断。"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO cycle_diagnoses 
        (date, short_term_stage, short_term_confidence,
         long_term_stage, long_term_confidence,
         empire_stage, empire_confidence, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date.today().isoformat(),
        short_stage, short_conf,
        long_stage, long_conf,
        empire_stage, empire_conf,
        json.dumps(detail or {}, ensure_ascii=False)
    ))
    conn.commit()
    conn.close()


def get_indicator_count() -> int:
    """统计有多少种指标。"""
    conn = get_conn()
    row = conn.execute("SELECT COUNT(DISTINCT indicator_name) as cnt FROM macro_indicators").fetchone()
    conn.close()
    return row["cnt"]


# 首次导入自动初始化
init_db()
