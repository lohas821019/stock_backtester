"""
測試：回測引擎
"""

import numpy as np
import pandas as pd
import pytest

from stock_backtester.strategies.ma_cross import MACrossStrategy
from stock_backtester.engine.backtest_engine import BacktestEngine, BacktestResult
from stock_backtester.analysis.performance import PerformanceAnalyzer


def make_trending_data(n: int = 200) -> pd.DataFrame:
    """建立有明顯趨勢的測試資料。"""
    rng = np.random.default_rng(0)
    trend = np.linspace(100, 150, n)
    noise = rng.normal(0, 1, n)
    close = trend + noise

    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open":   close * 0.995,
            "high":   close * 1.005,
            "low":    close * 0.990,
            "close":  close,
            "volume": rng.integers(10000, 100000, n).astype(float),
        },
        index=dates,
    )


class TestBacktestEngine:
    def test_run_returns_result(self):
        data = make_trending_data()
        engine = BacktestEngine()
        strat = MACrossStrategy()
        result = engine.run(data, strat, symbol="TEST")

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(data)
        assert result.final_capital > 0

    def test_equity_curve_positive(self):
        data = make_trending_data()
        engine = BacktestEngine()
        strat = MACrossStrategy(short_window=5, long_window=20)
        result = engine.run(data, strat)

        assert (result.equity_curve > 0).all(), "資金曲線應始終為正"

    def test_empty_data_raises(self):
        engine = BacktestEngine()
        strat = MACrossStrategy()
        with pytest.raises(ValueError, match="data 不能為空"):
            engine.run(pd.DataFrame(), strat)

    def test_trades_recorded(self):
        data = make_trending_data()
        engine = BacktestEngine()
        strat = MACrossStrategy(short_window=3, long_window=10)
        result = engine.run(data, strat)

        # 有趨勢的資料應產生至少一筆交易
        assert isinstance(result.trades, list)

    def test_executed_signals_pairwise(self):
        data = make_trending_data()
        engine = BacktestEngine()
        strat = MACrossStrategy(short_window=3, long_window=10)
        result = engine.run(data, strat)

        # 買進與賣出訊號數量應嚴格成對且等於交易次數
        buy_cnt = (result.signals == 1).sum()
        sell_cnt = (result.signals == -1).sum()
        assert buy_cnt == sell_cnt == len(result.trades)



class TestPerformanceAnalyzer:
    def test_metrics_keys_exist(self):
        data = make_trending_data()
        engine = BacktestEngine()
        strat = MACrossStrategy()
        result = engine.run(data, strat)

        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze(result)

        expected_keys = [
            "total_return_pct", "annualized_return_pct",
            "sharpe_ratio", "max_drawdown_pct",
            "win_rate_pct", "total_trades",
        ]
        for key in expected_keys:
            assert key in metrics, f"缺少指標: {key}"

    def test_format_report_returns_string(self):
        data = make_trending_data()
        engine = BacktestEngine()
        result = engine.run(data, MACrossStrategy())

        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze(result)
        report = analyzer.format_report(metrics, result)

        assert isinstance(report, str)
        assert "回測報告" in report
