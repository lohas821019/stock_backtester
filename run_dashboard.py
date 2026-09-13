#!/usr/bin/env python3
"""
啟動 Dashboard 的快捷腳本

使用方式：
    python3 run_dashboard.py
"""

import subprocess
import sys
from pathlib import Path

APP_PATH = Path(__file__).parent / "stock_backtester" / "dashboard" / "app.py"

if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(APP_PATH),
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ])
