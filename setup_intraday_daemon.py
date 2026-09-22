#!/usr/bin/env python3
"""
macOS 盤中實時進場雷達背景守護行程安裝工具 (macOS LaunchAgent Setup)

為使用者的 Mac 設定原生的 launchd 系統排程服務：
- 每週一至週五 08:55 自動在背景啟動盤中實時盯盤守護行程。
- 盤中每 20 秒極速檢測 TWSE 即時撮合。
- 0050 / 0052 碰觸突破或回踩價時，30 秒內發送 Telegram 急報與 Mac 桌面通知。
- 13:35 收盤後發送總結並自動休眠結束。

使用方式：
    python3 setup_intraday_daemon.py install    # 安裝並啟用背景守護行程
    python3 setup_intraday_daemon.py status     # 檢查守護行程運行狀態
    python3 setup_intraday_daemon.py uninstall  # 移除守護行程
    python3 setup_intraday_daemon.py run-now    # 立即在終端前景測試運行
"""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.stock_backtester.intraday_radar"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
PROJECT_DIR = Path(__file__).parent.resolve()
PYTHON_PATH = sys.executable
LOG_DIR = Path.home() / ".stock_backtester"
LOG_FILE = LOG_DIR / "intraday_radar.log"


def load_env_vars() -> dict[str, str]:
    """從 .env 讀取憑證環境變數。"""
    env_file = PROJECT_DIR / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars


def install():
    print("🚀 正在為 macOS 設定盤中實時雷達守護服務...")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    env_vars = load_env_vars()
    env_vars["PATH"] = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin")
    env_vars["PYTHONUNBUFFERED"] = "1"

    # 設定週一至週五 08:55 啟動
    calendar_intervals = [
        {"Weekday": day, "Hour": 8, "Minute": 55}
        for day in range(1, 6)  # 1=Monday, 5=Friday
    ]

    plist_data = {
        "Label": LABEL,
        "ProgramArguments": [
            PYTHON_PATH,
            "-m",
            "stock_backtester.cli",
            "watch-live",
            "--stocks",
            "0050,0052",
            "--notify",
            "--summary",
            "--interval",
            "60",
            "--max-alerts",
            "5",
            "--cooldown",
            "180",
            "--daemon",
        ],
        "WorkingDirectory": str(PROJECT_DIR),
        "EnvironmentVariables": env_vars,
        "StartCalendarInterval": calendar_intervals,
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
        "RunAtLoad": False,
    }

    # 若已有舊服務，先 unload
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)

    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist_data, f)

    res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✅ 服務已成功安裝並載入系統服務池！")
        print(f"   • Plist 路徑: {PLIST_PATH}")
        print(f"   • 執行時間: 每週一至週五 08:55 自動在背景啟動")
        print(f"   • 監控標的: 0050, 0052 (碰價 20 秒極速推播)")
        print(f"   • Log 輸出: {LOG_FILE}")
        print(f"\n💡 提示：您可隨時執行 'python3 setup_intraday_daemon.py status' 檢查狀態。")
    else:
        print(f"❌ 載入服務失敗: {res.stderr}")


def uninstall():
    print("🗑️ 正在移除盤中實時雷達守護服務...")
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink()
        print(f"✅ 服務已成功移除: {PLIST_PATH}")
    else:
        print("💡 未偵測到已安裝之服務。")


def status():
    print(f"🔍 檢查服務狀態: {LABEL}")
    res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    loaded = LABEL in res.stdout
    if loaded:
        print(f"🟢 【運行中 / 已載入】守護服務正常常駐中！")
        # 顯示 PID
        for line in res.stdout.splitlines():
            if LABEL in line:
                print(f"   系統進程資訊: {line}")
    else:
        if PLIST_PATH.exists():
            print(f"🟡 【已設定排程但目前未在執行】(將於週一至週五 08:55 自動喚醒)")
        else:
            print(f"⚪ 【未安裝】尚未安裝 LaunchAgent 服務。")

    if LOG_FILE.exists():
        print(f"\n📄 最新 Log 輸出 (最後 10 行)：")
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[-10:]
        for l in lines:
            print(f"   {l}")


def run_now():
    print("⚡ 立即在終端前景啟動盤中實時雷達...")
    cmd = [
        PYTHON_PATH,
        "-m",
        "stock_backtester.cli",
        "watch-live",
        "--stocks",
        "0050,0052",
        "--notify",
        "--summary",
        "--interval",
        "60",
        "--max-alerts",
        "5",
        "--cooldown",
        "180",
        "--daemon",
    ]
    subprocess.run(cmd, cwd=str(PROJECT_DIR))


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    elif action == "status":
        status()
    elif action == "run-now":
        run_now()
    else:
        print(f"未知指令: {action}")
        print("可用指令: install, uninstall, status, run-now")


if __name__ == "__main__":
    main()
