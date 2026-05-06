"""新浪财经数据抓取 — 独立脚本，不依赖项目导入（避免 WSL SQLite 慢）。"""
import requests
import json
import sqlite3
from datetime import date
from pathlib import Path

DB = Path(__file__).parent.parent / "macro.db"
HEADERS = {"Referer": "https://finance.sina.com.cn"}


def save(name, value, source="sina"):
    conn = sqlite3.connect(str(DB))
    today = date.today().isoformat()
    conn.execute("""
        INSERT INTO macro_indicators (indicator_name, value, date, source)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(indicator_name, date, source) DO UPDATE SET value=excluded.value
    """, (name, value, today, source))
    conn.commit()
    conn.close()


def fetch(tickers: list[str]) -> dict:
    """批量获取新浪报价。"""
    url = f"https://hq.sinajs.cn/list={'%2C'.join(tickers)}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    text = resp.content.decode("gbk")
    
    result = {}
    for line in text.strip().split("\n"):
        if "=" not in line:
            continue
        try:
            var = line.split("=")[0].replace("var hq_str_", "")
            parts = line.split('"')
            if len(parts) >= 3:
                result[var] = parts[1].split(",")
        except (IndexError, ValueError):
            continue
    return result


def main():
    today = date.today().isoformat()
    saved = 0
    
    # ═══ 1. 美股三大指数 ═══
    print("[1/4] 美股指数...")
    us = fetch(["gb_inx", "gb_dji", "gb_ixic"])
    
    idx_map = {
        "gb_inx": ("us_sp500", 1),
        "gb_dji": ("us_dow", 1),
        "gb_ixic": ("us_nasdaq", 1),
    }
    for ticker, (name, field) in idx_map.items():
        if ticker in us and len(us[ticker]) > field:
            try:
                save(name, float(us[ticker][field]))
                saved += 1
                print(f"  ✓ {name} = {us[ticker][field]}")
            except (ValueError, IndexError):
                print(f"  ✗ {name} parse error")
        else:
            print(f"  ✗ {name} no data")
    
    # ═══ 2. 黄金白银 ═══
    print("[2/4] 贵金属...")
    metals = fetch(["hf_XAU", "hf_XAG"])
    
    if "hf_XAU" in metals and len(metals["hf_XAU"]) > 0:
        try:
            save("gold", float(metals["hf_XAU"][0]))
            save("gold_prev_close", float(metals["hf_XAU"][7]))
            saved += 2
            print(f"  ✓ gold = {metals['hf_XAU'][0]} (昨收:{metals['hf_XAU'][7]})")
        except (ValueError, IndexError):
            print("  ✗ gold parse error")
    
    if "hf_XAG" in metals and len(metals["hf_XAG"]) > 0:
        try:
            save("silver", float(metals["hf_XAG"][0]))
            saved += 1
            print(f"  ✓ silver = {metals['hf_XAG'][0]}")
        except (ValueError, IndexError):
            print("  ✗ silver parse error")
    
    # ═══ 3. ETF 代理 ═══
    print("[3/4] 美国 ETF 代理...")
    etfs = fetch(["gb_spy", "gb_tlt", "gb_gld", "gb_uso"])
    
    etf_map = {
        "gb_spy": "us_spy",
        "gb_tlt": "us_tlt",
        "gb_gld": "us_gld",
        "gb_uso": "us_uso",
    }
    for ticker, name in etf_map.items():
        if ticker in etfs and len(etfs[ticker]) > 1:
            try:
                save(name, float(etfs[ticker][1]))
                saved += 1
                print(f"  ✓ {name} = {etfs[ticker][1]}")
            except (ValueError, IndexError):
                print(f"  ✗ {name} parse error")
    
    # ═══ 4. DXY 美元指数 ═══
    print("[4/4] 美元指数...")
    dxy = fetch(["gb_dxy"])
    if "gb_dxy" in dxy and len(dxy["gb_dxy"]) > 1:
        try:
            save("us_dxy", float(dxy["gb_dxy"][1]))
            saved += 1
            print(f"  ✓ us_dxy = {dxy['gb_dxy'][1]}")
        except (ValueError, IndexError):
            print("  ✗ us_dxy parse error")
    else:
        # 回退：用 UUP ETF 代理
        print("  ⚠ DXY 不可用，尝试 UUP...")
        uup = fetch(["gb_uup"])
        if "gb_uup" in uup and len(uup["gb_uup"]) > 1:
            try:
                save("us_dxy_proxy", float(uup["gb_uup"][1]))
                saved += 1
                print(f"  ✓ us_dxy_proxy(UUP) = {uup['gb_uup'][1]}")
            except:
                print("  ✗ UUP also failed")
    
    print(f"\n✅ 总计保存 {saved} 个指标 to {DB}")


if __name__ == "__main__":
    main()
