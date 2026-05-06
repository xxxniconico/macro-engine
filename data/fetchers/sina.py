"""新浪财经数据抓取 — 美股、商品、汇率。

数据源格式（来自 memory）：
  美股 gb_ticker: [1]=现价, [2]=涨跌幅%, [4]=涨跌额, [5]=最高, [6]=开盘, [7]=最低, [26]=昨收
  港股 rt_hk: [2]=开, [3]=昨收, [4]=高, [5]=低, [6]=现价, [7]=涨跌额, [8]=涨跌幅%, [12]=成交量
  贵金属 hf_XAU/hf_XAG: [0]=现价, [4]=高, [5]=低, [7]=昨收
"""

import requests
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.storage import save_indicator, get_latest


SINA_API = "https://hq.sinajs.cn"
HEADERS = {"Referer": "https://finance.sina.com.cn"}


def _fetch(tickers: list[str]) -> dict:
    """批量获取新浪报价，返回 {ticker: [values]}。"""
    url = f"{SINA_API}/list={'%2C'.join(tickers)}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    # 新浪返回 gbk 编码
    try:
        text = resp.content.decode("gbk")
    except Exception:
        text = resp.text
    
    result = {}
    for line in text.strip().split("\n"):
        if not line or "=" not in line:
            continue
        # var hq_str_gb_ixic="..."
        try:
            var_name = line.split("=")[0].replace("var hq_str_", "")
            data_str = line.split('"')[1] if '"' in line else ""
            if data_str:
                result[var_name] = data_str.split(",")
        except (IndexError, ValueError):
            continue
    return result


def fetch_us_market():
    """抓取美股关键指标：SPX、纳斯达克、道琼斯、黄金、白银。"""
    tickers = [
        "gb_ixic",     # 纳斯达克
        "gb_inx",      # 标普500
        "gb_dji",      # 道琼斯
        "hf_XAU",      # 黄金现货
        "hf_XAG",      # 白银现货
    ]
    
    data = _fetch(tickers)
    today = date.today().isoformat()
    results = {}
    
    # 纳斯达克: [1]=现价
    if "gb_ixic" in data and data["gb_ixic"] and len(data["gb_ixic"]) > 1:
        try:
            v = float(data["gb_ixic"][1])
            save_indicator("us_nasdaq", v, today, "sina")
            results["us_nasdaq"] = v
        except ValueError: pass
    
    # 标普500: [1]=现价
    if "gb_inx" in data and data["gb_inx"] and len(data["gb_inx"]) > 1:
        try:
            v = float(data["gb_inx"][1])
            save_indicator("us_sp500", v, today, "sina")
            results["us_sp500"] = v
        except ValueError: pass
    
    # 道琼斯: [1]=现价
    if "gb_dji" in data and data["gb_dji"] and len(data["gb_dji"]) > 1:
        try:
            v = float(data["gb_dji"][1])
            save_indicator("us_dow", v, today, "sina")
            results["us_dow"] = v
        except ValueError: pass
    
    # 黄金: [0]=现价
    if "hf_XAU" in data and data["hf_XAU"] and len(data["hf_XAU"]) > 0:
        try:
            v = float(data["hf_XAU"][0])
            save_indicator("gold", v, today, "sina")
            results["gold"] = v
        except ValueError: pass
    
    return results


def fetch_dxy_and_bonds():
    """抓取美元指数和美债收益率。"""
    tickers = [
        "gb_dxy",      # 美元指数
        "gb_tyx",      # 10Y 美债收益率（近似）
    ]
    
    data = _fetch(tickers)
    today = date.today().isoformat()
    results = {}
    
    if "gb_dxy" in data:
        try:
            v = float(data["gb_dxy"][1])
            save_indicator("us_dxy", v, today, "sina")
            results["us_dxy"] = v
        except (ValueError, IndexError):
            pass
    
    if "gb_tyx" in data:
        try:
            v = float(data["gb_tyx"][1])
            save_indicator("us_10y_yield", v, today, "sina")
            results["us_10y_yield"] = v
        except (ValueError, IndexError):
            pass
    
    return results


def fetch_us_macro_proxy():
    """抓取美国宏观数据代理指标（CPI、GDP、失业率等通过新浪ETF等方式）。
    
    注：新浪财经 gb_ 系列不直接提供 CPI、GDP 等宏观数据。
    这里抓取能直接拿到的代理指标：
    - TLT (长期国债ETF) → 代理长期利率
    - GLD (黄金ETF) → 通胀预期代理
    - USO (原油ETF) → 能源价格
    """
    tickers = ["gb_tlt", "gb_gld", "gb_uso", "gb_spy"]
    data = _fetch(tickers)
    today = date.today().isoformat()
    results = {}
    
    for code, name in [("gb_tlt", "us_tlt"), ("gb_gld", "us_gld"), 
                        ("gb_spy", "us_spy"), ("gb_uso", "us_uso")]:
        if code in data:
            try:
                v = float(data[code][1])
                save_indicator(name, v, today, "sina")
                results[name] = v
            except (ValueError, IndexError):
                pass
    
    return results


def fetch_all():
    """一键抓取所有新浪数据。"""
    results = {}
    try:
        results.update(fetch_us_market())
    except Exception as e:
        print(f"[sina] us_market error: {e}")
    try:
        results.update(fetch_dxy_and_bonds())
    except Exception as e:
        print(f"[sina] dxy error: {e}")
    try:
        results.update(fetch_us_macro_proxy())
    except Exception as e:
        print(f"[sina] macro_proxy error: {e}")
    
    print(f"[sina] saved {len(results)} indicators: {list(results.keys())}")
    return results


if __name__ == "__main__":
    fetch_all()
