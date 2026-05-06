#!/bin/bash
# Dalio 宏观引擎 V3 — 全指标覆盖
set -e
cd "$(dirname "$0")"
PY=~/.hermes/hermes-agent/venv/bin/python
echo "════════════════════════════════════"
echo "  Dalio 宏观周期定位引擎 V3"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════"

echo "[1/5] 新浪财经 V5（全指标：美股+黄金+ETF+VIX+DXY代理+利率曲线）..."
$PY data/fetchers/sina_v5.py

echo "[2/5] 东方财富（宏观数据 PMI/CPI）..."
$PY data/fetchers/eastmoney_macro.py

echo "[3/5] World Bank（长期数据，已有则跳过）..."
$PY data/fetchers/worldbank.py

echo "[4/5] 周期诊断..."
$PY engine/cycle_locator.py

echo "[5/5] 历史模板匹配..."
$PY engine/template_matcher.py

echo "Done ✓"
