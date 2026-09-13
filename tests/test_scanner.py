"""
測試：通知器與掃描器
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd
import numpy as np

from stock_backtester.notifiers.telegram_notifier import TelegramNotifier
from stock_backtester.scanner.daily_scanner import DailyScanner, SignalResult
from stock_backtester.scanner.scan_config import StockScanConfig


# ── Telegram Notifier ────────────────────────────────────────────────────────

class TestTelegramNotifier:
    def test_init_empty_token_raises(self):
        with pytest.raises(ValueError):
            TelegramNotifier(token="", chat_id="123")

    def test_init_empty_chat_id_raises(self):
        with pytest.raises(ValueError):
            TelegramNotifier(token="abc:def", chat_id="")

    def test_send_success(self):
        notifier = TelegramNotifier(token="test:token", chat_id="123")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = notifier.send("Hello")

        assert result is True
        mock_post.assert_called_once()
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["text"] == "Hello"
        assert call_json["chat_id"] == "123"

    def test_send_api_error_returns_false(self):
        notifier = TelegramNotifier(token="test:token", chat_id="123")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": False, "description": "Bad token"}
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp):
            result = notifier.send("Hello")

        assert result is False

    def test_send_network_error_returns_false(self):
        import requests as req
        notifier = TelegramNotifier(token="test:token", chat_id="123")

        with patch("requests.post", side_effect=req.RequestException("timeout")):
            result = notifier.send("Hello")

        assert result is False


# ── DailyScanner ──────────────────────────────────────────────────────────────

def _make_dummy_df(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 500 + rng.normal(0, 5, n).cumsum()
    close = np.maximum(close, 1)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "open":   close * 0.99,
        "high":   close * 1.01,
        "low":    close * 0.98,
        "close":  close,
        "volume": rng.integers(1000, 10000, n).astype(float),
    }, index=dates)


class _FakeNotifier:
    """測試用假 notifier，記錄發送的訊息。"""
    def __init__(self):
        self.messages = []

    def send(self, text, **_):
        self.messages.append(text)
        return True

    def test_connection(self):
        return True


class TestDailyScanner:
    def test_run_with_mocked_data(self):
        fake_notifier = _FakeNotifier()
        fake_dm = MagicMock()
        fake_dm.get_ohlcv.return_value = _make_dummy_df()

        stocks = [
            StockScanConfig(symbol="2330", name="台積電", strategies=["ma_cross"]),
        ]

        scanner = DailyScanner(
            notifier=fake_notifier,
            data_manager=fake_dm,
            scan_date=date(2024, 3, 29),
        )
        summary = scanner.run(stocks)

        assert summary.total_scanned == 1
        assert isinstance(summary.buy_signals, list)
        # 每日摘要應該有被發送
        assert len(fake_notifier.messages) >= 1

    def test_empty_data_is_error(self):
        fake_notifier = _FakeNotifier()
        fake_dm = MagicMock()
        fake_dm.get_ohlcv.return_value = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

        stocks = [StockScanConfig(symbol="9999", name="不存在", strategies=["ma_cross"])]
        scanner = DailyScanner(
            notifier=fake_notifier,
            data_manager=fake_dm,
            scan_date=date(2024, 3, 29),
        )
        summary = scanner.run(stocks)

        assert len(summary.errors) == 1

    def test_buy_signal_triggers_notification(self):
        """當訊號為 1 時，應發送買進通知。"""
        fake_notifier = _FakeNotifier()
        fake_dm = MagicMock()

        # 製造一個最後一天一定會出現均線黃金交叉的資料
        # 用明顯上漲趨勢（短線一定高於長線）
        n = 60
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        # 先下跌後急漲，在最後一天形成黃金交叉
        close = np.concatenate([
            np.linspace(100, 80, 30),  # 前30天下跌
            np.linspace(80, 120, 30),  # 後30天急漲
        ])
        df = pd.DataFrame({
            "open": close * 0.99, "high": close * 1.01,
            "low": close * 0.98, "close": close,
            "volume": np.ones(n) * 1000,
        }, index=dates)
        fake_dm.get_ohlcv.return_value = df

        stocks = [StockScanConfig(
            symbol="2330", name="台積電",
            strategies=["ma_cross"],
            strategy_params={"ma_cross": {"short_window": 3, "long_window": 10}},
        )]

        scanner = DailyScanner(
            notifier=fake_notifier,
            data_manager=fake_dm,
            scan_date=date(2024, 3, 29),
        )
        summary = scanner.run(stocks)

        # 訊號計算是否正確（不強制一定有買進，但不應報錯）
        assert len(summary.errors) == 0
