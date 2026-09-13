#!/usr/bin/env python3
"""
每日掃描入口腳本

此腳本由排程器（cron）每日自動呼叫：
    每天 15:00 台股收盤後執行（或美股盤後）

使用方式：
    python3 run_daily_scan.py

設定步驟：
    1. 複製 .env.example 為 .env
    2. 填入 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID
    3. 依需求修改 stock_backtester/scanner/scan_config.py 的股票清單
    4. 設定 cron 排程（見下方說明）

設定 cron（每天 15:05 台北時間執行）：
    1. 在終端機執行：crontab -e
    2. 加入以下這一行（請替換路徑）：
       5 15 * * 1-5 cd /Users/huang/Documents/stock_backtester && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 run_daily_scan.py >> ~/.stock_backtester/scan.log 2>&1
    3. 儲存並關閉編輯器

    說明：
    - 5 15 * * 1-5 = 週一到週五 15:05
    - >> ~/.stock_backtester/scan.log = 記錄 log 到檔案
"""

import logging
import os
import sys
from pathlib import Path

# 確保可以找到套件
sys.path.insert(0, str(Path(__file__).parent))

# 載入 .env
def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print(f"[錯誤] 找不到 .env 檔案：{env_path}")
        print("請複製 .env.example 為 .env 並填入 Telegram 憑證。")
        sys.exit(1)

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

_load_env()

# 設定 logging
log_dir = Path.home() / ".stock_backtester"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "scan.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("run_daily_scan")


def main() -> None:
    from stock_backtester.notifiers.telegram_notifier import TelegramNotifier
    from stock_backtester.scanner.daily_scanner import DailyScanner
    from stock_backtester.scanner.scan_config import SCAN_STOCKS

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or bot_token == "your_bot_token_here":
        logger.error("請在 .env 設定 TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    if not chat_id or chat_id == "your_chat_id_here":
        logger.error("請在 .env 設定 TELEGRAM_CHAT_ID")
        sys.exit(1)

    notifier = TelegramNotifier(token=bot_token, chat_id=chat_id)

    # 測試連線
    if not notifier.test_connection():
        logger.error("Telegram Bot 連線失敗，請確認 TOKEN 是否正確")
        sys.exit(1)

    scanner = DailyScanner(notifier=notifier)
    summary = scanner.run(SCAN_STOCKS)

    logger.info(
        "掃描完成 | 掃描: %d 支 | 買進訊號: %d 支 | 錯誤: %d",
        summary.total_scanned,
        len(set(r.symbol for r in summary.buy_signals)),
        len(summary.errors),
    )


if __name__ == "__main__":
    main()
