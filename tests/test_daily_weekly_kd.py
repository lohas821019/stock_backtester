"""
測試：日 KD 與 週 KD 策略
"""

import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies import get_strategy
from stock_backtester.strategies.daily_kd import DailyKDStrategy
from stock_backtester.strategies.weekly_kd import WeeklyKDStrategy
from stock_backtester.engine.backtest_engine import BacktestEngine


def make_test_data(n_days: int = 250) -> pd.DataFrame:
    """產生約 1 年的日線測試資料（含明顯波動以觸發超買超賣）。"""
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


class TestDailyKDStrategy:
    def test_registered_name(self):
        cls = get_strategy("daily_kd")
        assert cls is DailyKDStrategy

    def test_generate_signals(self):
        data = make_test_data(250)
        strategy = DailyKDStrategy(oversold_threshold=20.0, overbought_threshold=80.0)
        signals = strategy.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})
        # 有波動數據應能觸發買賣訊號
        assert (signals == 1).sum() > 0
        assert (signals == -1).sum() > 0

    def test_engine_run(self):
        data = make_test_data(250)
        strategy = DailyKDStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strategy, symbol="TEST")

        assert len(result.trades) > 0
        assert len(result.equity_curve) == len(data)


class TestWeeklyKDStrategy:
    def test_registered_name(self):
        cls = get_strategy("weekly_kd")
        assert cls is WeeklyKDStrategy

    def test_generate_signals(self):
        data = make_test_data(250)
        strategy = WeeklyKDStrategy(oversold_threshold=20.0, overbought_threshold=80.0)
        signals = strategy.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})

    def test_short_data_graceful(self):
        short_data = make_test_data(10)
        strategy = WeeklyKDStrategy()
        signals = strategy.generate_signals(short_data)
        assert (signals == 0).all()

    def test_engine_run(self):
        data = make_test_data(250)
        strategy = WeeklyKDStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strategy, symbol="TEST")

        assert len(result.equity_curve) == len(data)
