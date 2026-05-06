#!/bin/bash
# Dalio 宏观引擎 — 全模块 (V3+P1+P2)
set -e
cd "$(dirname "$0")"
PY=~/.hermes/hermes-agent/venv/bin/python
echo "════════════════════════════════════"
echo "  Dalio 宏观引擎 V3+P1+P2"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════"

echo "[1/10] 新浪财经 V5..."
$PY data/fetchers/sina_v5.py

echo "[2/10] 东方财富宏观..."
$PY data/fetchers/eastmoney_macro.py

echo "[3/10] World Bank..."
$PY data/fetchers/worldbank.py

echo "[4/10] 周期定位..."
$PY engine/cycle_locator.py

echo "[5/10] 历史模板匹配..."
$PY engine/template_matcher.py

echo "[6/10] 因果链条..."
$PY engine/causal_chain.py

echo "[7/10] 压力测试..."
$PY engine/stress_test.py

echo "[8/10] 叙事分析..."
$PY engine/narrative.py

echo "[9/10] 多方博弈..."
$PY engine/game_theory.py

echo "[10/10] 系统动力..."
$PY engine/system_dynamics.py

echo "Done ✓"
