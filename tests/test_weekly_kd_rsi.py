"""
測試：週 KD + 週 RSI 策略與 0050 成分股模組
"""

import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies.weekly_kd_rsi import WeeklyKdRsiStrategy
from stock_backtester.data.constituents import (
    TAIWAN_50_STOCKS,
    TAIWAN_50_MAP,
    get_taiwan_50_symbols,
)
from stock_backtester.strategies import get_strategy


def make_multi_week_data(n_days: int = 250) -> pd.DataFrame:
    """產生約 1 年 (50 週) 的日線測試資料。"""
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    trend = np.linspace(100, 180, n_days)
    noise = rng.normal(0, 1.5, n_days)
    close = trend + noise

    return pd.DataFrame({
        "open":   close * 0.99,
        "high":   close * 1.015,
        "low":    close * 0.985,
        "close":  close,
        "volume": rng.integers(10000, 50000, n_days).astype(float),
    }, index=dates)


class TestWeeklyKdRsiStrategy:
    def test_registered_name(self):
        cls = get_strategy("weekly_kd_rsi")
        assert cls is WeeklyKdRsiStrategy

    def test_generate_signals_structure(self):
        data = make_multi_week_data(250)
        strategy = WeeklyKdRsiStrategy(
            kd_rsv_window=9,
            kd_k_window=3,
            kd_d_window=3,
            rsi_window=14,
            oversold_threshold=20.0,
            overbought_threshold=90.0,
        )
        signals = strategy.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})

    def test_short_data_graceful(self):
        """資料量太短時應安全回傳全 0 訊號。"""
        short_data = make_multi_week_data(10)
        strategy = WeeklyKdRsiStrategy()
        signals = strategy.generate_signals(short_data)
        assert (signals == 0).all()


class TestTaiwan50Constituents:
    def test_constituents_count(self):
        """0050 ETF 本身 + 50 檔成分股 = 51 檔。"""
        assert len(TAIWAN_50_STOCKS) >= 50
        assert "0050" in TAIWAN_50_MAP
        assert "2330" in TAIWAN_50_MAP  # 台積電
        assert "2454" in TAIWAN_50_MAP  # 聯發科
        assert "2317" in TAIWAN_50_MAP  # 鴻海

    def test_symbols_helper(self):
        symbols = get_taiwan_50_symbols()
        assert "0050" in symbols
        assert "2330" in symbols
