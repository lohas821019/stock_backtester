"""
測試：月線與週線鈍化策略（Monthly KD, Monthly RSI, Upgraded Weekly RSI）
"""

import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies import get_strategy
from stock_backtester.strategies.monthly_kd_passivation import MonthlyKDPassivationStrategy
from stock_backtester.strategies.monthly_rsi import MonthlyRSIStrategy
from stock_backtester.strategies.weekly_rsi import WeeklyRSIStrategy
from stock_backtester.engine.backtest_engine import BacktestEngine


def make_multiyear_data(n_days: int = 800) -> pd.DataFrame:
    """產生跨數年的日線測試資料（含大波段趨勢以觸發月線與週線指標）。"""
    dates = pd.date_range("2022-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)
    p1 = int(n_days * 0.3)
    p2 = int(n_days * 0.5)
    p3 = n_days - p1 - p2
    trend = np.concatenate([
        np.linspace(100, 70, p1),
        np.linspace(70, 200, p2),
        np.linspace(200, 160, p3),
    ])
    close = trend + rng.normal(0, 1.0, n_days)

    return pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": rng.integers(10000, 50000, n_days).astype(float),
    }, index=dates)


class TestMonthlyKDPassivation:
    def test_registered_name(self):
        cls = get_strategy("monthly_kd_passivation")
        assert cls is MonthlyKDPassivationStrategy
        # ALIAS check
        cls_alias = get_strategy("monthly_kd")
        assert cls_alias is MonthlyKDPassivationStrategy

    def test_signals_structure(self):
        data = make_multiyear_data(800)
        strat = MonthlyKDPassivationStrategy()
        signals = strat.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert (signals == 1).sum() > 0

    def test_engine_run(self):
        data = make_multiyear_data(800)
        strat = MonthlyKDPassivationStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strat, symbol="MONTHLY_TEST")

        assert len(result.trades) > 0
        assert len(result.equity_curve) == len(data)


class TestMonthlyRSI:
    def test_registered_name(self):
        cls = get_strategy("monthly_rsi")
        assert cls is MonthlyRSIStrategy

    def test_signals_structure(self):
        data = make_multiyear_data(800)
        strat = MonthlyRSIStrategy()
        signals = strat.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert (signals == 1).sum() > 0

    def test_engine_run(self):
        data = make_multiyear_data(800)
        strat = MonthlyRSIStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strat, symbol="MONTHLY_RSI_TEST")

        assert len(result.trades) > 0
        assert len(result.equity_curve) == len(data)


class TestWeeklyRSIUpgraded:
    def test_signals_structure(self):
        data = make_multiyear_data(500)
        strat = WeeklyRSIStrategy()
        signals = strat.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert (signals == 1).sum() > 0

    def test_engine_run(self):
        data = make_multiyear_data(500)
        strat = WeeklyRSIStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strat, symbol="WEEKLY_RSI_TEST")

        assert len(result.trades) > 0
        assert len(result.equity_curve) == len(data)
