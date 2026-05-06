#!/bin/bash
# Dalio 宏观引擎 — 完整运行脚本 V3
set -e
cd "$(dirname "$0")"
PY=~/.hermes/hermes-agent/venv/bin/python
echo "════════════════════════════════════"
echo "  Dalio 宏观周期定位引擎"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════"

echo "[1/6] 新浪财经（美股/黄金）..."
$PY data/fetchers/sina_v4.py

echo "[2/6] 东方财富（A股行情）..."
$PY -c "from data.fetchers.eastmoney import fetch_all; fetch_all()" 2>/dev/null

echo "[3/6] 东方财富（宏观数据）..."
$PY data/fetchers/eastmoney_macro.py

echo "[4/6] World Bank（长期数据，已有则跳过）..."
$PY data/fetchers/worldbank.py

echo "[5/6] 周期诊断..."
$PY engine/cycle_locator.py

echo "[6/6] 历史模板匹配..."
$PY engine/template_matcher.py

echo "Done ✓"
