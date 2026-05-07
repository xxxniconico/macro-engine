#!/bin/bash
# ═══════════════════════════════════════════════
# 管线刷新 — 被各层更新脚本调用
# 引擎重算 → data.json 导出 → 看板就绪
# ═══════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/refresh_$(date +%Y%m%d_%H%M).log"

echo "  ── 管线刷新 $(date '+%H:%M:%S') ──" | tee -a "$LOG"

# ── 1. 导出 data.json (内含 orchestrator 全量重算) ──
echo "  [a] 导出 data.json + 引擎重算..." | tee -a "$LOG"
python3 dashboard/export_data.py 2>&1 | tee -a "$LOG"

# ── 2. 验证 data.json ──
if [ -f dashboard/data.json ]; then
    SIZE=$(stat -c%s dashboard/data.json 2>/dev/null || echo 0)
    echo "  ✓ data.json ${SIZE} bytes" | tee -a "$LOG"
else
    echo "  ✗ data.json 未生成！" | tee -a "$LOG"
    exit 1
fi

echo "  ✅ 管线刷新完成 $(date '+%H:%M:%S')" | tee -a "$LOG"
