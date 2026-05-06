"""东方财富数据抓取 — 中国宏观经济数据。

数据源：东方财富 push2 API
格式：http://push2.eastmoney.com/api/qt/stock/get?secid=...
"""

import requests
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.storage import save_indicator


EM_API = "https://push2.eastmoney.com/api/qt/stock/get"


def _fetch_em(secid: str, fields: str = "f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f116,f117,f161,f162,f169,f170") -> dict | None:
    """通用东方财富行情抓取。
    
    关键字段：
      f43: 最新价  f44: 最高  f45: 最低  f46: 开盘
      f47: 成交量  f48: 成交额  f50: 量比  f57: 名称
      f170: 涨跌幅
    """
    params = {
        "secid": secid,
        "fields": fields,
        "ut": "fa5fd1943c1e3e4e9e9e9e9e9e9e9e9e",
    }
    resp = requests.get(EM_API, params=params, timeout=10)
    data = resp.json()
    if data.get("data"):
        return data["data"]
    return None


def fetch_china_market():
    """抓取 A 股主要指数。"""
    today = date.today().isoformat()
    results = {}
    
    indices = {
        "1.000001": "china_sh_index",    # 上证指数
        "0.399001": "china_sz_index",    # 深证成指
        "0.399006": "china_chinext",     # 创业板指
        "1.000688": "china_star_market", # 科创50
    }
    
    for secid, name in indices.items():
        data = _fetch_em(secid)
        if data and "f43" in data:
            v = data["f43"] / 100  # EM push2 f43 单位是分
            save_indicator(name, v, today, "eastmoney")
            results[name] = v
    
    return results


def fetch_china_macro():
    """抓取中国宏观经济代理指标。
    
    注：东方财富 push2 API 主要用于行情数据。
    真正的宏观数据（CPI、PMI、M2）需要通过其他方式获取。
    这里先用 A股行业 ETF 作为代理：
    - 房地产 ETF → 代理房地产景气度
    - 银行 ETF → 代理金融系统健康度
    - 消费 ETF → 代理消费信心
    """
    today = date.today().isoformat()
    results = {}
    
    etf_map = {
        "1.512200": "china_realestate_etf",   # 房地产ETF
        "1.512800": "china_bank_etf",         # 银行ETF
        "1.510150": "china_consumer_etf",     # 消费ETF
        "1.510050": "china_50etf",            # 上证50
        "1.510300": "china_300etf",           # 沪深300
    }
    
    for secid, name in etf_map.items():
        data = _fetch_em(secid)
        if data and "f43" in data:
            v = data["f43"]
            save_indicator(name, v, today, "eastmoney")
            results[name] = v
    
    return results


def fetch_macro_manual() -> dict:
    """手动录入的宏观数据占位符。
    
    TODO: 接入国家统计局 API 或爬取东方财富数据中心页面。
    当前阶段，这些数据需要手动从以下渠道获取后录入：
    - PMI: https://data.eastmoney.com/cjsj/pmi.html
    - CPI: https://data.eastmoney.com/cjsj/cpi.html
    - M2: https://data.eastmoney.com/cjsj/hbgyl.html
    - GDP: https://data.eastmoney.com/cjsj/gdp.html
    
    手动录入格式：
      save_indicator("china_pmi", 50.5, "2026-04-01", "manual")
      save_indicator("china_cpi", 0.2, "2026-04-01", "manual")
      save_indicator("china_m2_yoy", 7.0, "2026-04-01", "manual")
    """
    return {}


def fetch_all():
    """一键抓取所有东方财富数据。"""
    results = {}
    try:
        results.update(fetch_china_market())
    except Exception as e:
        print(f"[eastmoney] market error: {e}")
    try:
        results.update(fetch_china_macro())
    except Exception as e:
        print(f"[eastmoney] macro error: {e}")
    
    print(f"[eastmoney] saved {len(results)} indicators: {list(results.keys())}")
    return results


if __name__ == "__main__":
    fetch_all()
