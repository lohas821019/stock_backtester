#!/usr/bin/env python3
"""
cron 排程設定工具

執行此腳本即可自動設定每日掃描的 crontab 排程。

使用方式：
    python3 setup_cron.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
PYTHON     = sys.executable
SCRIPT     = PROJECT_DIR / "run_daily_scan.py"
LOG_FILE   = Path.home() / ".stock_backtester" / "scan.log"

# ── 可調整的排程時間 ──────────────────────────────────────────────────
# 格式：(分, 時)，採本機時間（macOS 預設使用本機時區）
# 建議：台股 15:05（盤後5分鐘），或 15:10 更穩定
CRON_MINUTE = 10
CRON_HOUR   = 15
# 只在週一到週五執行（1-5）
CRON_DOW    = "1-5"
# ──────────────────────────────────────────────────────────────────────

CRON_LINE = (
    f"{CRON_MINUTE} {CRON_HOUR} * * {CRON_DOW} "
    f"cd {PROJECT_DIR} && {PYTHON} {SCRIPT} "
    f">> {LOG_FILE} 2>&1"
)

MARKER = "# stock-backtester daily scan"


def read_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""  # 尚未有 crontab
    return result.stdout


def write_crontab(content: str) -> None:
    proc = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True)
    if proc.returncode != 0:
        print(f"[錯誤] 寫入 crontab 失敗：{proc.stderr}")
        sys.exit(1)


def main():
    print("📅 設定每日掃描 cron 排程")
    print(f"   腳本路徑：{SCRIPT}")
    print(f"   執行時間：週一至週五 {CRON_HOUR:02d}:{CRON_MINUTE:02d}")
    print(f"   Log 位置：{LOG_FILE}")
    print()

    existing = read_crontab()

    if MARKER in existing:
        print("⚠️  偵測到已有排程，是否覆蓋？（y/N）", end=" ")
        ans = input().strip().lower()
        if ans != "y":
            print("取消，未做任何更改。")
            return

        # 移除舊排程（含 MARKER 的那幾行）
        lines = [
            line for line in existing.splitlines()
            if MARKER not in line and not (line.strip() and CRON_LINE.split(" >> ")[0] in line)
        ]
        existing = "\n".join(lines) + "\n"

    # 確保 log 目錄存在
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    new_crontab = existing.rstrip("\n") + f"\n{MARKER}\n{CRON_LINE}\n"
    write_crontab(new_crontab)

    print("✅ 排程設定完成！")
    print()
    print("驗證指令：")
    print("   crontab -l           # 查看目前排程")
    print("   python3 run_daily_scan.py   # 立即手動執行一次")
    print(f"   tail -f {LOG_FILE}  # 監看 log")
    print()
    print("移除排程：")
    print("   crontab -e  # 手動編輯刪除 stock-backtester 那兩行")


if __name__ == "__main__":
    main()
