#!/bin/bash
# ═══════════════════════════════════════════════
# 每年更新 — Tier 4: 结构指标 (10指标)
# 运行频率: 每年1月15日 08:00
# 数据源:   World Bank Gini + COFER + 手动
# ═══════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/annual_$(date +%Y%m%d_%H%M).log"

echo "═══ 每年结构更新 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

# ── 1. Gini + COFER 补齐 ──
echo "[1/3] Gini + COFER 数据..." | tee -a "$LOG"
python3 data/backfill_gini_cofer.py 2>&1 | tee -a "$LOG"

# ── 2. World Bank 全量 ──
echo "[2/3] World Bank 全量..." | tee -a "$LOG"
python3 data/fetchers/worldbank.py 2>&1 | tee -a "$LOG"

# ── 3. 引擎 + 看板刷新 ──
echo "[3/3] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ 每年更新完成 $(date '+%H:%M')" | tee -a "$LOG"
