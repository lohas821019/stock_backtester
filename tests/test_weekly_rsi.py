"""
測試：週 RSI 策略
"""

import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies import get_strategy
from stock_backtester.strategies.weekly_rsi import WeeklyRSIStrategy
from stock_backtester.engine.backtest_engine import BacktestEngine


def make_test_data(n_days: int = 250) -> pd.DataFrame:
    """產生約 1 年的日線測試資料（含循環波動以觸發超買超賣）。"""
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(123)
    cycle = 30 * np.sin(np.linspace(0, 8 * np.pi, n_days))
    close = 100 + cycle + rng.normal(0, 1.0, n_days)

    return pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": rng.integers(10000, 50000, n_days).astype(float),
    }, index=dates)


class TestWeeklyRSIStrategy:
    def test_registered_name(self):
        cls = get_strategy("weekly_rsi")
        assert cls is WeeklyRSIStrategy

    def test_generate_signals_structure(self):
        data = make_test_data(250)
        strategy = WeeklyRSIStrategy(period=14, oversold=30.0, overbought=70.0)
        signals = strategy.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})

    def test_short_data_graceful(self):
        short_data = make_test_data(10)
        strategy = WeeklyRSIStrategy()
        signals = strategy.generate_signals(short_data)
        assert (signals == 0).all()

    def test_engine_run(self):
        data = make_test_data(250)
        strategy = WeeklyRSIStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strategy, symbol="TEST")

        assert len(result.equity_curve) == len(data)
