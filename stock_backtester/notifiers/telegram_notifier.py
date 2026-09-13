"""
Telegram 通知器

使用 Telegram Bot API 發送訊息（直接呼叫 REST API，無需額外套件）。

設定步驟：
    1. 在 Telegram 搜尋 @BotFather，輸入 /newbot 建立 Bot，取得 BOT_TOKEN
    2. 對你的 Bot 傳送任意訊息，然後用瀏覽器開啟：
       https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
       從回應中找到 "chat": {"id": ...} 即為 CHAT_ID
    3. 在 .env 檔案填入 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID
"""

import logging
import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    """
    Telegram Bot 通知器。

    使用範例：
        notifier = TelegramNotifier(token="123:ABC...", chat_id="987654321")
        notifier.send("🚀 台積電 2330 出現買進訊號！")
    """

    def __init__(self, token: str, chat_id: str):
        """
        Args:
            token:   Telegram Bot Token（從 @BotFather 取得）
            chat_id: 接收訊息的 Chat ID（個人或群組）
        """
        if not token or not chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID 不能為空")
        self._token = token
        self._chat_id = chat_id

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        發送文字訊息。

        Args:
            text:       訊息內容（支援 HTML 或 Markdown 格式）
            parse_mode: "HTML" 或 "Markdown"

        Returns:
            True = 發送成功，False = 失敗
        """
        url = _API_BASE.format(token=self._token, method="sendMessage")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                logger.error("[Telegram] 發送失敗: %s", result)
                return False
            logger.info("[Telegram] 訊息發送成功")
            return True
        except requests.RequestException as e:
            logger.error("[Telegram] 請求失敗: %s", e)
            return False

    def test_connection(self) -> bool:
        """
        測試 Bot 連線是否正常。

        Returns:
            True = 連線成功
        """
        url = _API_BASE.format(token=self._token, method="getMe")
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                bot_name = data["result"].get("username", "unknown")
                logger.info("[Telegram] Bot 連線成功: @%s", bot_name)
                return True
        except requests.RequestException as e:
            logger.error("[Telegram] 連線測試失敗: %s", e)
        return False
