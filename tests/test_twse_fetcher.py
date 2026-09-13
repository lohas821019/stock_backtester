"""
測試：TWSE 資料抓取器
"""

from datetime import date
import pandas as pd
import pytest

from stock_backtester.data.fetchers.twse_fetcher import TWSEFetcher


class TestTWSEFetcher:
    def test_fetch_tsmc_daily(self):
        """測試抓取台積電日線資料。"""
        fetcher = TWSEFetcher()
        df = fetcher.fetch("2330", date(2024, 1, 1), date(2024, 1, 31))

        assert not df.empty, "應取得資料"
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df["close"].iloc[0] > 0
        assert len(df) >= 15, "1 月應有至少 15 個交易日"

    def test_invalid_interval_raises(self):
        """非日線 interval 應拋出 ValueError。"""
        fetcher = TWSEFetcher()
        with pytest.raises(ValueError, match="僅支援日線"):
            fetcher.fetch("2330", date(2024, 1, 1), date(2024, 1, 31), interval="5min")

    def test_fetch_returns_normalized_columns(self):
        """欄位名稱應為小寫。"""
        fetcher = TWSEFetcher()
        df = fetcher.fetch("2330", date(2024, 3, 1), date(2024, 3, 31))
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns, f"缺少欄位: {col}"
