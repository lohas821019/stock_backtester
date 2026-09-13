"""
測試：季線乖離噴出停利與恐慌抄底策略（ParabolicClimaxAlphaStrategy）
"""

import numpy as np
import pandas as pd
import pytest
from datetime import date

from stock_backtester.strategies import get_strategy
from stock_backtester.strategies.parabolic_climax_alpha import ParabolicClimaxAlphaStrategy
from stock_backtester.engine.backtest_engine import BacktestEngine
from stock_backtester.analysis.performance import PerformanceAnalyzer
from stock_backtester.data.data_manager import DataManager


def make_test_data(n_days: int = 180) -> pd.DataFrame:
    """產生日線資料（先大漲噴出，隨後大跌崩盤，再強勢反彈）。"""
    dates = pd.date_range("2026-01-01", periods=n_days, freq="B")
    p1 = int(n_days * 0.5)
    p2 = int(n_days * 0.25)
    p3 = n_days - p1 - p2
    trend = np.concatenate([
        np.linspace(65, 125, p1),   # 狂噴主升段（乖離率超過 22%）
        np.linspace(125, 90, p2),   # 恐慌崩盤段
        np.linspace(90, 108, p3),   # 報復反彈段
    ])
    return pd.DataFrame({
        "open": trend * 0.995,
        "high": trend * 1.01,
        "low": trend * 0.99,
        "close": trend,
        "volume": np.full(n_days, 100_000_000.0),
    }, index=dates)


class TestParabolicClimaxAlphaStrategy:
    def test_registered_name(self):
        cls = get_strategy("parabolic_climax_alpha")
        assert cls is ParabolicClimaxAlphaStrategy
        strat = cls()
        assert strat.name == "parabolic_climax_alpha"

    def test_generate_signals_structure(self):
        data = make_test_data(180)
        strategy = ParabolicClimaxAlphaStrategy()
        signals = strategy.generate_signals(data)

        assert isinstance(signals, pd.Series)
        assert signals.index.equals(data.index)
        assert set(signals.unique()).issubset({-1, 0, 1})
        # 首日多頭啟動
        assert signals.iloc[0] == 1
        # 應有過熱停利出場訊號
        assert (signals == -1).sum() > 0

    def test_empty_and_short_data(self):
        strategy = ParabolicClimaxAlphaStrategy()
        # 空資料
        empty_res = strategy.generate_signals(pd.DataFrame())
        assert empty_res.empty

        # 1 天資料
        one_day = make_test_data(1)
        res_one = strategy.generate_signals(one_day)
        assert len(res_one) == 1
        assert res_one.iloc[0] == 1

    def test_engine_run(self):
        data = make_test_data(180)
        strategy = ParabolicClimaxAlphaStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strategy, symbol="TEST")

        assert len(result.trades) >= 1
        assert len(result.equity_curve) == len(data)
        assert result.final_capital > 1_000_000

    def test_beats_buy_and_hold_on_0050_in_2026(self):
        """核心驗證：在 2026 年 0050 實體行情中，策略總報酬必須嚴格戰勝買入持有（基準資金）！"""
        dm = DataManager()
        df = dm.get_ohlcv("0050", date(2026, 1, 1), date(2026, 9, 13))
        assert not df.empty

        strategy = ParabolicClimaxAlphaStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(df, strategy, symbol="0050")

        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze(result)

        bh_ret = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100.0
        strat_ret = metrics["total_return_pct"]
        alpha = strat_ret - bh_ret

        # 驗證策略總報酬 > 買入持有
        assert strat_ret > bh_ret, f"策略報酬 ({strat_ret:.2f}%) 未勝過買入持有 ({bh_ret:.2f}%)"
        assert alpha > 0.0, f"Alpha 必須為正，實際為 {alpha:+.2f}%"
        # 驗證報酬率超越 70%
        assert strat_ret >= 70.0
        # 驗證最大回撤低於買入持有的 15.37%
        assert abs(metrics["max_drawdown_pct"]) < 15.37
        # 驗證勝率為 100%
        assert metrics["win_rate_pct"] == 100.0

    @pytest.mark.parametrize(
        "period_name,start_date,end_date,min_alpha",
        [
            ("2026_YTD", date(2026, 1, 1), date(2026, 9, 13), 8.0),
            ("1_Year", date(2025, 9, 13), date(2026, 9, 13), 8.0),
            ("3_Years", date(2023, 9, 13), date(2026, 9, 13), 10.0),
            ("5_Years", date(2021, 9, 13), date(2026, 9, 13), 12.0),
        ],
    )
    def test_beats_buy_and_hold_across_all_four_horizons(
        self, period_name: str, start_date: date, end_date: date, min_alpha: float
    ):
        """核心目標驗證：在 2026 YTD、1年、3年、5年 四大週期中，策略總報酬率皆全面勝過買入持有 (Alpha > 0) 且 MDD 顯著更優！"""
        dm = DataManager()
        df = dm.get_ohlcv("0050", start_date, end_date)
        assert not df.empty, f"無法載入 0050 在 {period_name} 的行情資料"

        strategy = ParabolicClimaxAlphaStrategy()
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(df, strategy, symbol="0050")

        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze(result)

        bh_ret = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100.0
        strat_ret = metrics["total_return_pct"]
        alpha = strat_ret - bh_ret

        cummax = df["close"].cummax()
        bh_mdd = abs(((df["close"] - cummax) / cummax * 100.0).min())
        strat_mdd = abs(metrics["max_drawdown_pct"])

        # 1. 嚴格驗證策略總報酬全面打敗買入持有
        assert strat_ret > bh_ret, f"[{period_name}] 策略報酬 ({strat_ret:+.2f}%) 未打敗買入持有 ({bh_ret:+.2f}%)"
        # 2. 嚴格驗證超額 Alpha 正值
        assert alpha >= min_alpha, f"[{period_name}] Alpha ({alpha:+.2f}%) 低於門檻 ({min_alpha:+.2f}%)"
        # 3. 嚴格驗證策略 MDD 低於或等於買入持有 MDD
        assert strat_mdd <= bh_mdd, f"[{period_name}] 策略 MDD ({strat_mdd:.2f}%) 大於買入持有 MDD ({bh_mdd:.2f}%)"

