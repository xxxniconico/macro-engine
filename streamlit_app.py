"""Streamlit Cloud 入口 — 指向 dashboard/app.py"""

import sys
from pathlib import Path

# 确保项目根在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

# 直接执行 dashboard/app.py
exec(open(Path(__file__).parent / "dashboard" / "app.py", encoding="utf-8").read())
