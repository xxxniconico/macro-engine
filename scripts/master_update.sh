#!/bin/bash
# ═══════════════════════════════════════════════════════
# Dalio 宏观模型 — 分层自动更新策略
# ═══════════════════════════════════════════════════════
#
# 数据层级:
#   Tier 1 — 每日 (交易日):   新浪行情 15 指标
#   Tier 2 — 每月 (1日):      PMI + CPI + 失业率 8 指标 (EastMoney/手动)
#   Tier 3 — 每季 (首月5日):   GDP + 债务/GDP 7 指标 (World Bank)
#   Tier 4 — 每年 (1月15日):   Gini + 百年数据 + COFER 10+ 指标 (WB/WID/JST)
#
# Cron 配置 (建议):
#   0 8 * * 1-5  cd ~/macro-engine && bash scripts/update_daily.sh      # 交易日 8AM
#   0 8 1 * *    cd ~/macro-engine && bash scripts/update_monthly.sh    # 每月1日 8AM
#   0 8 5 1,4,7,10 * cd ~/macro-engine && bash scripts/update_quarterly.sh  # 季初
#   0 8 15 1 *   cd ~/macro-engine && bash scripts/update_annual.sh     # 每年1月15日
#
# 手动全量:  bash scripts/master_update.sh all
# 手动单层:  bash scripts/master_update.sh daily|monthly|quarterly|annual
# ═══════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M)
MAIN_LOG="$LOG_DIR/master_${TIMESTAMP}.log"

log() {
    echo "[$(date '+%H:%M:%S')] $*" | tee -a "$MAIN_LOG"
}

run_tier() {
    local tier=$1
    local script="$SCRIPT_DIR/update_${tier}.sh"
    if [ -f "$script" ]; then
        log "▶ 开始 Tier: $tier"
        bash "$script" 2>&1 | tee -a "$MAIN_LOG" || log "⚠ Tier $tier 有错误（继续）"
        log "✓ Tier $tier 完成"
    else
        log "✗ 脚本不存在: $script"
    fi
}

case "${1:-all}" in
    daily)
        run_tier "daily"
        ;;
    monthly)
        run_tier "monthly"
        ;;
    quarterly)
        run_tier "quarterly"
        ;;
    annual)
        run_tier "annual"
        ;;
    all)
        log "═══ 全量更新开始 ═══"
        run_tier "annual"
        run_tier "quarterly"
        run_tier "monthly"
        run_tier "daily"
        log "═══ 全量更新完成 ═══"
        ;;
    *)
        echo "Usage: $0 {daily|monthly|quarterly|annual|all}"
        exit 1
        ;;
esac

# 统计
DATA_COUNT=$(python3 -c "
import sqlite3,json
conn=sqlite3.connect('$PROJECT_DIR/macro.db')
c=conn.cursor()
c.execute('SELECT COUNT(*), COUNT(DISTINCT indicator_name), MAX(date) FROM macro_indicators')
r=c.fetchone()
print(f'{r[0]}条 | {r[1]}指标 | 最新:{r[2][:10]}')
conn.close()
")
log "📊 当前数据库: $DATA_COUNT"
log "✅ 完成"
