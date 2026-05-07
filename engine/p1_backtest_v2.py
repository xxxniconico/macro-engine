#!/usr/bin/env python3
"""
P1 Backtest V2 — uses full orchestrator with time-filtered data.
Creates temp DB copies with data only up to each crisis date,
then runs the full pipeline.
"""
import sqlite3
import json
import sys
import os
import shutil
from pathlib import Path
from datetime import date

PROJ_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ_ROOT))
DB_PATH = PROJ_ROOT / "macro.db"

TEMPLATES = [
    ("1997 Asian Financial",   "1997-07-02", "crisis_unfolding", 55, 85),
    ("1998 LTCM/Russia",       "1998-08-17", "crisis_unfolding", 50, 80),
    ("2000 Dot-com Peak",      "2000-03-10", "bubble_forming",   45, 75),
    ("2001 9/11",              "2001-09-11", "crisis_unfolding", 50, 80),
    ("2008 GFC (Lehman)",      "2008-09-15", "crisis_unfolding", 70, 95),
    ("2010 EU Sovereign Debt", "2010-05-02", "crisis_unfolding", 55, 85),
    ("2013 Taper Tantrum",     "2013-06-19", "crisis_unfolding", 40, 70),
    ("2015 China Stock Crash", "2015-08-24", "crisis_unfolding", 45, 75),
    ("2018 Q4 Selloff",        "2018-12-24", "crisis_unfolding", 40, 70),
    ("2020 COVID Crash",       "2020-03-16", "crisis_unfolding", 70, 95),
    ("2022 Russia-Ukraine",    "2022-02-24", "crisis_unfolding", 55, 85),
    ("2023 SVB Collapse",      "2023-03-10", "crisis_unfolding", 45, 75),
    ("2024 Aug VIX Spike",     "2024-08-05", "crisis_unfolding", 40, 70),
]

def run_backtest_v2():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA busy_timeout=10000")

    results = []
    print("📊 P1 Backtest V2 — Full Orchestrator\n")
    print(f"{'':3s} {'Crisis':<25s} {'Date':>12s} {'Risk':>5s} {'Phase':<18s} {'Match':>20s}")
    print("-"*90)

    for name, crisis_date, exp_phase, exp_min, exp_max in TEMPLATES:
        # Count indicators available at this date
        n = db.execute("SELECT COUNT(DISTINCT indicator_name) FROM macro_indicators WHERE date <= ?", (crisis_date,)).fetchone()[0]

        if n < 8:
            results.append({
                'name': name, 'date': crisis_date, 'risk_score': None,
                'expected_range': f'{exp_min}-{exp_max}',
                'match': f'data_insufficient ({n} inds)',
                'n_indicators': n,
            })
            print(f"  ❌ {name:<25s} {crisis_date:>12s} {'--':>5s} {'--':<18s} {'数据不足('+str(n)+'指标)':>20s}")
            continue

        # Create temp DB with only pre-crisis data
        tmp_db = PROJ_ROOT / f"macro_backtest_{crisis_date.replace('-','')}.db"
        if tmp_db.exists():
            tmp_db.unlink()

        tmp_conn = sqlite3.connect(str(tmp_db))
        # Copy schema (skip internal tables)
        for row in db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"):
            tmp_conn.execute(row[0])
        # Copy ONLY pre-crisis data
        pre_rows = db.execute("SELECT * FROM macro_indicators WHERE date <= ?", (crisis_date,)).fetchall()
        cols = [d[0] for d in db.execute("PRAGMA table_info(macro_indicators)")]
        placeholders = ','.join(['?'] * len(cols))
        for row in pre_rows:
            tmp_conn.execute(f"INSERT INTO macro_indicators({','.join(cols)}) VALUES({placeholders})", row)
        tmp_conn.commit()
        n_copied = len(pre_rows)

        # Temporarily swap DB
        real_db = DB_PATH
        backup_db = Path(str(real_db) + '.p1_backup')
        shutil.copy2(real_db, backup_db)
        shutil.copy2(tmp_db, real_db)

        # Run full orchestrator
        try:
            from engine.orchestrator import run_full_pipeline
            orch = run_full_pipeline(skip_narrative_crawl=True)
            syn = orch.get('results', {}).get('synthesis', {})
            risk_score = syn.get('risk_score', None)
            detected_phase = orch.get('detected_phase', '?')

            if risk_score is not None:
                if exp_min <= risk_score <= exp_max:
                    match = '✓ hit'
                    icon = '✅'
                elif risk_score < exp_min:
                    match = f'⚠ low (-{exp_min - risk_score})'
                    icon = '⚠️'
                else:
                    match = f'⚠ high (+{risk_score - exp_max})'
                    icon = '⚠️'
            else:
                match = 'error'
                icon = '❌'

            results.append({
                'name': name, 'date': crisis_date, 'risk_score': risk_score,
                'phase': detected_phase, 'expected_range': f'{exp_min}-{exp_max}',
                'match': match, 'n_indicators': n,
            })

            print(f"  {icon} {name:<25s} {crisis_date:>12s} {str(risk_score):>5s} {detected_phase:<18s} {match:>20s}")

        except Exception as e:
            results.append({
                'name': name, 'date': crisis_date, 'risk_score': None,
                'expected_range': f'{exp_min}-{exp_max}',
                'match': f'error: {str(e)[:40]}',
                'n_indicators': n,
            })
            print(f"  ❌ {name:<25s} {crisis_date:>12s} {'--':>5s} {'--':<18s} {'error':>20s}")

        finally:
            # Restore real DB
            shutil.copy2(backup_db, real_db)
            backup_db.unlink()
            tmp_db.unlink()
            tmp_conn.close()

    # Stats
    hits = sum(1 for r in results if 'hit' in r.get('match', ''))
    valid = sum(1 for r in results if r['risk_score'] is not None)
    accuracy = hits / valid * 100 if valid > 0 else 0

    print(f'\n{"="*60}')
    print(f'📊 Backtest Results: {hits}/{valid} hits ({accuracy:.0f}% accuracy)')
    print(f'   Total templates tested: {len(TEMPLATES)}')
    print(f'   Insufficient data: {len(TEMPLATES) - valid}')

    db.close()
    return {'results': results, 'accuracy': round(accuracy, 1), 'total': len(TEMPLATES), 'valid': valid, 'hits': hits}

if __name__ == '__main__':
    run_backtest_v2()
