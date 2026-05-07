#!/bin/bash
# Tier 1 — 每日行情更新（交易日）
# 指标: SP500/Dow/Nasdaq, Gold, SPY/TLT/GLD/USO, VIXY/UUP/SHY/IEF/EEM
#      利率曲线(SHY/IEF比值), 上证指数
# 来源: 新浪 hq.sinajs.cn
# cron: 0 8 * * 1-5
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily_$(date +%Y%m%d_%H%M).log"

echo "═══ Tier 1 每日行情 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

# 1. 新浪美股 + 贵金属 + ETF + 利率曲线
echo "[1/3] 新浪行情 (15指标)..." | tee -a "$LOG"
python3 data/fetchers/sina_v5.py 2>&1 | tee -a "$LOG"

# 2. 上证指数
echo "[2/3] 上证指数..." | tee -a "$LOG"
python3 -c "
import subprocess, sqlite3
from datetime import date
r = subprocess.run(['curl','-s','--max-time','8',
    '-H','Referer: https://finance.sina.com.cn',
    'https://hq.sinajs.cn/list=sh000001'],
    capture_output=True, timeout=10)
line = r.stdout.decode('gbk')
if '=' in line:
    d = line.split('\"')[1].split(',')
    price = float(d[1])
    conn = sqlite3.connect('$PROJECT_DIR/macro.db')
    conn.execute('''INSERT INTO macro_indicators(indicator_name,value,date,source)
        VALUES(?,?,?,?) ON CONFLICT(indicator_name,date,source)
        DO UPDATE SET value=excluded.value''',
        ('china_sh_index', price, date.today().isoformat(), 'sina'))
    conn.commit(); conn.close()
    print(f'  ✓ china_sh_index = {price}')
" 2>&1 | tee -a "$LOG"

# 3. 重新跑引擎 + 导出看板
echo "[3/3] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ Tier 1 完成 $(date '+%H:%M')" | tee -a "$LOG"
