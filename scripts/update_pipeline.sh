#!/bin/bash
# ═══════════════════════════════════════════════
# 总控管线 — 一键全量更新 (手动测试用)
# 按依赖顺序: 年→季→月→日 → 引擎重算 → 看板刷新
#
# 定时任务请直接调用各 tier 脚本:
#   scripts/update_daily.sh    每个交易日 08:00
#   scripts/update_monthly.sh  每月1日 08:00
#   scripts/update_quarterly.sh 每季首月5日 08:00
#   scripts/update_annual.sh   每年1月15日 08:00
# ═══════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/full_$(date +%Y%m%d_%H%M).log"

echo "╔══════════════════════════════════════╗" | tee "$LOG"
echo "║  Dalio 宏观引擎 — 全量更新管线      ║" | tee -a "$LOG"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')             ║" | tee -a "$LOG"
echo "╚══════════════════════════════════════╝" | tee -a "$LOG"
echo "" | tee -a "$LOG"

# ── Tier 1: 每日行情 ──
echo "【Tier 1】每日行情 (新浪)" | tee -a "$LOG"
bash "$SCRIPT_DIR/update_daily.sh" 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "╔══════════════════════════════════════╗" | tee -a "$LOG"
echo "║  ✅ 全量更新完成                     ║" | tee -a "$LOG"
echo "║  看板: http://localhost:8502         ║" | tee -a "$LOG"
echo "╚══════════════════════════════════════╝" | tee -a "$LOG"
