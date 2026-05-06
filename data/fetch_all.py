"""数据抓取入口 — 一键抓取所有源。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.fetchers import sina, eastmoney


def fetch_all():
    """抓取所有数据源。"""
    results = {}
    
    print("=" * 50)
    print("Dalio 宏观引擎 — 数据抓取")
    print("=" * 50)
    
    print("\n[1/2] 新浪财经...")
    results.update(sina.fetch_all())
    
    print("\n[2/2] 东方财富...")
    results.update(eastmoney.fetch_all())
    
    print(f"\n总计: {len(results)} 个指标已更新")
    return results


if __name__ == "__main__":
    fetch_all()
