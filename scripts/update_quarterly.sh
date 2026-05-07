#!/bin/bash
# ═══════════════════════════════════════════════
# 每季更新 — Tier 3: GDP/债务 (7指标)
# 运行频率: 每季首月5日 08:00 (1/5, 4/5, 7/5, 10/5)
# 数据源:   World Bank + 手动
# ═══════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/quarterly_$(date +%Y%m%d_%H%M).log"

echo "═══ 每季宏观更新 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

# ── 1. World Bank 全量 ──
echo "[1/2] World Bank 全量数据..." | tee -a "$LOG"
python3 data/fetchers/worldbank.py 2>&1 | tee -a "$LOG"

# ── 2. 引擎 + 看板刷新 ──
echo "[2/2] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ 每季更新完成 $(date '+%H:%M')" | tee -a "$LOG"
