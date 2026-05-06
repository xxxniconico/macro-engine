#!/bin/bash
# Dalio 宏观引擎 V3 + P1 — 全模块
set -e
cd "$(dirname "$0")"
PY=~/.hermes/hermes-agent/venv/bin/python
echo "════════════════════════════════════"
echo "  Dalio 宏观周期定位引擎 V3+P1"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════"

echo "[1/7] 新浪财经 V5..."
$PY data/fetchers/sina_v5.py

echo "[2/7] 东方财富宏观..."
$PY data/fetchers/eastmoney_macro.py

echo "[3/7] World Bank..."
$PY data/fetchers/worldbank.py

echo "[4/7] 周期定位..."
$PY engine/cycle_locator.py

echo "[5/7] 历史模板匹配..."
$PY engine/template_matcher.py

echo "[6/7] 因果链条..."
$PY engine/causal_chain.py

echo "[7/7] 压力测试..."
$PY engine/stress_test.py

echo "Done ✓"
