"""
測試：週 KD 鈍化波段趨勢守護策略
"""

import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies import get_strategy
from stock_backtester.strategies.weekly_kd_passivation import WeeklyKDPassivationStrategy
from stock_backtester.engine.backtest_engine import BacktestEngine


def make_test_data(n_days: int = 300) -> pd.DataFrame:
    """產生日線資料（含持續上漲波段以觸發高檔鈍化）。"""
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    if n_days >= 100:
        p1 = int(n_days * 0.2)
        p2 = int(n_days * 0.6)
        p3 = n_days - p1 - p2
        trend = np.concatenate([
            np.linspace(100, 70, p1),
            np.linspace(70, 180, p2),
            np.linspace(180, 140, p3),
        ])
    else:
        trend = np.linspace(100, 150, n_days)
    close = trend + rng.normal(0, 1.0, n_days)

    return pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": rng.integers(10000, 50000, n_days).astype(float),
    }, index=dates)


class TestWeeklyKDPassivationStrategy:
    def test_registered_name(self):
        cls = get_strategy("weekly_kd_passivation")
        assert cls is WeeklyKDPassivationStrategy

    def test_generate_signals_structure(self):
        data = make_test_data(300)
        strategy = WeeklyKDPassivationStrategy()
        signals = strategy.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})
        # 有明顯波段應能觸發買進與出場
        assert (signals == 1).sum() > 0
        assert (signals == -1).sum() > 0

    def test_short_data_graceful(self):
        short_data = make_test_data(15)
        strategy = WeeklyKDPassivationStrategy()
        signals = strategy.generate_signals(short_data)
        assert (signals == 0).all()

    def test_engine_run(self):
        data = make_test_data(300)
        strategy = WeeklyKDPassivationStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strategy, symbol="PASSIVATION_TEST")

        assert len(result.trades) > 0
        assert len(result.equity_curve) == len(data)

    def test_parameters_and_flags(self):
        data = make_test_data(300)
        s1 = WeeklyKDPassivationStrategy(allow_passivation_entry=True, allow_trend_cross=True)
        s2 = WeeklyKDPassivationStrategy(allow_passivation_entry=False, allow_trend_cross=False)

        sig1 = s1.generate_signals(data)
        sig2 = s2.generate_signals(data)

        assert isinstance(sig1, pd.Series)
        assert isinstance(sig2, pd.Series)
        assert (sig1 == 1).sum() >= (sig2 == 1).sum()

