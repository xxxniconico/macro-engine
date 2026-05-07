#!/bin/bash
# Tier 2 — 每月宏观数据更新
# 指标: china_pmi, us_pmi, china_cpi, us_cpi, china_unemployment, us_unemployment
# 来源: EastMoney 数据中心 + World Bank API + 手动估算
# cron: 0 8 1 * *
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/monthly_$(date +%Y%m%d_%H%M).log"

echo "═══ Tier 2 每月宏观 $(date '+%Y-%m-%d %H:%M') ═══" | tee "$LOG"

# 1. 中国 PMI (EastMoney)
echo "[1/4] 中国 PMI..." | tee -a "$LOG"
python3 -c "
import urllib.request, json, sqlite3
from datetime import date

conn = sqlite3.connect('$PROJECT_DIR/macro.db')
c = conn.cursor()

# EastMoney 中国制造业 PMI
url = 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_PMI&columns=REPORT_DATE,INDICATOR_ID,INDICATOR_NAME,DATA_VALUE&filter=(INDICATOR_ID=%22EMI00107664%22)&pageNumber=1&pageSize=5&sortTypes=-1&sortColumns=REPORT_DATE'
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get('success') and data.get('result') and data['result'].get('data'):
        for r in data['result']['data']:
            dt = r['REPORT_DATE'][:10] if 'T' not in r['REPORT_DATE'] else r['REPORT_DATE'][:10]
            val = float(r['DATA_VALUE'])
            c.execute('''INSERT OR REPLACE INTO macro_indicators(indicator_name,value,date,source)
                VALUES(?,?,?,?)''', ('china_pmi', val, dt, 'eastmoney_dc'))
            print(f'  ✓ china_pmi {dt} = {val}')
        conn.commit()
        print(f'  PMI updated from EastMoney')
    else:
        print('  ⚠ EastMoney PMI API 返回异常')
except Exception as e:
    print(f'  ✗ EastMoney PMI: {e}')

conn.close()
" 2>&1 | tee -a "$LOG"

# 2. US PMI (手动填入 — ISM 每月第1个工作日发布)
echo "[2/4] 美国 PMI..." | tee -a "$LOG"
echo "  ℹ ISM PMI 需手动更新（每月第1个工作日发布）" | tee -a "$LOG"
echo "    编辑: data/manual/monthly_values.json" | tee -a "$LOG"
# 从手动文件读取（如果存在）
if [ -f data/manual/monthly_values.json ]; then
    python3 -c "
import json, sqlite3
conn = sqlite3.connect('$PROJECT_DIR/macro.db')
with open('data/manual/monthly_values.json') as f:
    mv = json.load(f)
c = conn.cursor()
for name, val in mv.items():
    if val:
        c.execute('''INSERT OR REPLACE INTO macro_indicators(indicator_name,value,date,source)
            VALUES(?,?,date('now','start of month'),?)''', (name, val, 'manual'))
        print(f'  ✓ {name} = {val}')
conn.commit(); conn.close()
" 2>&1 | tee -a "$LOG"
fi

# 3. World Bank monthly indicators (CPI, unemployment)
echo "[3/4] World Bank 月度指标..." | tee -a "$LOG"
python3 -c "
import urllib.request, json, sqlite3, time

conn = sqlite3.connect('$PROJECT_DIR/macro.db')
c = conn.cursor()

# WB indicators that update more frequently
indicators = [
    ('china_cpi', 'FP.CPI.TOTL.ZG', 'CN'),   # Inflation
    ('us_cpi', 'FP.CPI.TOTL.ZG', 'US'),
    ('china_unemployment', 'SL.UEM.TOTL.ZS', 'CN'),
    ('us_unemployment', 'SL.UEM.TOTL.ZS', 'US'),
]

for name, code, country in indicators:
    try:
        url = f'https://api.worldbank.org/v2/country/{country}/indicator/{code}?format=json&per_page=5'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if len(data) >= 2 and data[1]:
            for item in data[1]:
                if item.get('value'):
                    yr = item['year']
                    val = float(item['value'])
                    dt = f'{yr}-12-01'
                    c.execute('''INSERT OR REPLACE INTO macro_indicators(indicator_name,value,date,source)
                        VALUES(?,?,?,?)''', (name, val, dt, 'worldbank'))
            print(f'  ✓ {name} ({country}) updated')
        time.sleep(0.5)
    except Exception as e:
        print(f'  ⚠ {name}: {e}')
conn.commit(); conn.close()
" 2>&1 | tee -a "$LOG"

# 4. 管线刷新
echo "[4/4] 管线刷新..." | tee -a "$LOG"
bash "$SCRIPT_DIR/refresh_pipeline.sh" 2>&1 | tee -a "$LOG"

echo "✅ Tier 2 完成 $(date '+%H:%M')" | tee -a "$LOG"
