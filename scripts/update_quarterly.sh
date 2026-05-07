#!/bin/bash
# Tier 3 — 每季宏观数据更新
# 指标: GDP增速, 债务/GDP (中美)
# 来源: World Bank API
# cron: 0 8 5 1,4,7,10 *
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/quarterly_$(date +%Y%m%d_%H%M).log"

echo "═══ Tier 3 每季宏观 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

echo "[1/3] World Bank GDP + 债务..." | tee -a "$LOG"
python3 -c "
import urllib.request, json, sqlite3, time

conn = sqlite3.connect('$PROJECT_DIR/macro.db')
c = conn.cursor()

indicators = [
    # GDP growth
    ('china_gdp_growth', 'NY.GDP.MKTP.KD.ZG', 'CN'),
    ('us_gdp_growth', 'NY.GDP.MKTP.KD.ZG', 'US'),
    # Government debt/GDP
    ('us_govt_debt_gdp', 'GC.DOD.TOTL.GD.ZS', 'US'),
]

for name, code, country in indicators:
    try:
        url = f'https://api.worldbank.org/v2/country/{country}/indicator/{code}?format=json&per_page=50'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        if len(data) >= 2 and data[1]:
            for item in data[1]:
                if item.get('value'):
                    yr = item['year']
                    val = float(item['value'])
                    c.execute('''INSERT OR REPLACE INTO macro_indicators(indicator_name,value,date,source)
                        VALUES(?,?,?,?)''', (name, val, f'{yr}-12-31', 'worldbank'))
            c.execute('SELECT COUNT(*), MAX(date) FROM macro_indicators WHERE indicator_name=? AND source=?',
                      (name, 'worldbank'))
            cnt, latest = c.fetchone()
            print(f'  ✓ {name}: {cnt} records, latest={latest}')
        time.sleep(0.5)
    except Exception as e:
        print(f'  ⚠ {name}: {e}')

# China debt/GDP (估算 — WB 不全)
print(f'  ℹ china_debt_gdp 需手动更新（IMF GFS 数据不全）')

conn.commit(); conn.close()
" 2>&1 | tee -a "$LOG"

echo "[2/3] 手动指标检查..." | tee -a "$LOG"
echo "  ℹ 以下需手动更新（季报发布后）：" | tee -a "$LOG"
echo "    - china_debt_gdp (IMF GFS / 中国央行)" | tee -a "$LOG"
echo "    - us_debt_gdp (Treasury Direct)" | tee -a "$LOG"
echo "    - us_fed_rate (FOMC 决议后更新)" | tee -a "$LOG"

echo "[3/3] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ Tier 3 完成 $(date '+%H:%M')" | tee -a "$LOG"
