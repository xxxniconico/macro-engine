#!/bin/bash
# ═══════════════════════════════════════════════
# 每日更新 — Tier 1: 实时行情 (15指标)
# 运行频率: 每个交易日 08:00
# 数据源:   新浪财经 hq.sinajs.cn
# ═══════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily_$(date +%Y%m%d_%H%M).log"

echo "═══ 每日行情更新 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

# ── 1. 新浪行情 ──
echo "[1/2] 新浪行情抓取..." | tee -a "$LOG"
python3 data/fetchers/sina_v5.py 2>&1 | tee -a "$LOG"

# ── 2. 引擎 + 看板刷新 ──
echo "[2/2] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ 每日更新完成 $(date '+%H:%M')" | tee -a "$LOG"
