#!/bin/bash
# ═══════════════════════════════════════════════
# 每月更新 — Tier 2: 宏观发布 (8指标)
# 运行频率: 每月1日 08:00
# 数据源:   东方财富数据中心 + 手动补充
# ═══════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/monthly_$(date +%Y%m%d_%H%M).log"

echo "═══ 每月宏观更新 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

# ── 1. 东方财富宏观 ──
echo "[1/4] 东方财富宏观..." | tee -a "$LOG"
python3 data/fetchers/eastmoney_macro.py 2>&1 | tee -a "$LOG"

# ── 2. 美国月度宏观 ──
echo "[2/4] 美国月度宏观..." | tee -a "$LOG"
python3 data/fetchers/us_monthly.py 2>&1 | tee -a "$LOG"

# ── 3. World Bank 补充 ──
echo "[3/4] World Bank 数据补充..." | tee -a "$LOG"
python3 data/fetchers/worldbank.py 2>&1 | tee -a "$LOG"

# ── 4. 引擎 + 看板刷新 ──
echo "[4/4] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ 每月更新完成 $(date '+%H:%M')" | tee -a "$LOG"
