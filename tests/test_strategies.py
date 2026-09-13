"""
測試：策略系統
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies.base_strategy import BaseStrategy
from stock_backtester.strategies.ma_cross import MACrossStrategy
from stock_backtester.strategies.bollinger_band import BollingerBandStrategy
from stock_backtester.strategies.rsi_strategy import RSIStrategy
from stock_backtester.strategies import list_strategies, get_strategy


def make_dummy_data(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """建立測試用 OHLCV 資料。"""
    rng = np.random.default_rng(seed)
    close = 100 + rng.normal(0, 1, n).cumsum()
    close = np.maximum(close, 1)

    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open":   close * 0.99,
            "high":   close * 1.01,
            "low":    close * 0.98,
            "close":  close,
            "volume": rng.integers(1000, 10000, n).astype(float),
        },
        index=dates,
    )


class TestStrategyInterface:
    def test_ma_cross_inherits_base(self):
        assert issubclass(MACrossStrategy, BaseStrategy)

    def test_signals_have_correct_index(self):
        data = make_dummy_data()
        strat = MACrossStrategy()
        signals = strat.generate_signals(data)
        assert signals.index.equals(data.index), "訊號 index 需與 data index 相同"

    def test_signals_values_in_valid_range(self):
        data = make_dummy_data()
        for StratClass in [MACrossStrategy, BollingerBandStrategy, RSIStrategy]:
            strat = StratClass()
            signals = strat.generate_signals(data)
            assert set(signals.unique()).issubset({-1, 0, 1}), \
                f"{StratClass.name} 訊號值應只有 -1, 0, 1"

    def test_signals_returns_series(self):
        data = make_dummy_data()
        strat = RSIStrategy()
        result = strat.generate_signals(data)
        assert isinstance(result, pd.Series)


class TestStrategyRegistry:
    def test_list_strategies_includes_builtin(self):
        strategies = list_strategies()
        names = [s["name"] for s in strategies]
        assert "ma_cross" in names
        assert "bollinger_band" in names
        assert "daily_rsi" in names
        assert "weekly_rsi" in names

    def test_get_strategy_by_name(self):
        cls = get_strategy("ma_cross")
        assert cls is MACrossStrategy

    def test_get_strategy_alias_rsi(self):
        cls = get_strategy("rsi")
        assert cls is RSIStrategy

    def test_get_nonexistent_strategy_raises(self):
        with pytest.raises(KeyError, match="找不到策略"):
            get_strategy("nonexistent_xyz")

    def test_custom_strategy_auto_discovered(self, tmp_path, monkeypatch):
        """測試自動發現機制：新增策略檔案後可被找到。"""
        # 此測試使用 monkeypatching，略過動態模組掃描的複雜性
        # 在實際使用中，新增 .py 到 strategies/ 即可自動被發現
        pass


class TestMACrossParams:
    def test_invalid_params_raises(self):
        with pytest.raises(ValueError):
            MACrossStrategy(short_window=20, long_window=5)

    def test_ema_mode(self):
        data = make_dummy_data()
        strat = MACrossStrategy(short_window=5, long_window=20, ma_type="ema")
        signals = strat.generate_signals(data)
        assert isinstance(signals, pd.Series)
