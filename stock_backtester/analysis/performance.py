"""
績效分析器

計算回測結果的各項績效指標。
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from ..engine.backtest_engine import BacktestResult

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


class PerformanceAnalyzer:
    """
    績效分析器。

    使用範例：
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze(result)
        print(metrics)
    """

    def analyze(self, result: "BacktestResult") -> dict:
        """
        計算完整績效指標。

        Returns:
            包含所有績效指標的 dict
        """
        equity = result.equity_curve
        trades = result.trades
        initial = result.initial_capital
        final = result.final_capital

        metrics: dict = {}

        # ── 基本績效 ────────────────────────────────────────────────────────
        metrics["initial_capital"]   = initial
        metrics["final_capital"]     = final
        metrics["total_return_pct"]  = (final / initial - 1) * 100
        metrics["total_pnl"]         = final - initial

        # ── 年化報酬 ────────────────────────────────────────────────────────
        n_days = max((equity.index[-1] - equity.index[0]).days, 1)
        n_years = n_days / 365
        metrics["annualized_return_pct"] = (
            ((final / initial) ** (1 / n_years) - 1) * 100
            if n_years > 0 else 0.0
        )

        # ── 日報酬率序列 ────────────────────────────────────────────────────
        daily_returns = equity.pct_change().dropna()

        # ── Sharpe Ratio（無風險利率假設 1.5%）────────────────────────────
        risk_free_daily = 0.015 / TRADING_DAYS_PER_YEAR
        excess_returns = daily_returns - risk_free_daily
        std = excess_returns.std()
        metrics["sharpe_ratio"] = (
            float((excess_returns.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR))
            if (len(trades) > 0 and std > 1e-5) else 0.0
        )

        # ── 最大回撤 (MDD) ──────────────────────────────────────────────────
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        metrics["max_drawdown_pct"] = drawdown.min() * 100
        metrics["max_drawdown_duration_days"] = self._mdd_duration(drawdown)

        # ── Calmar Ratio ────────────────────────────────────────────────────
        mdd = abs(metrics["max_drawdown_pct"]) / 100
        metrics["calmar_ratio"] = (
            metrics["annualized_return_pct"] / 100 / mdd if mdd > 0 else 0.0
        )

        # ── 交易統計 ────────────────────────────────────────────────────────
        metrics["total_trades"] = len(trades)

        if trades:
            pnls = [t.pnl for t in trades]
            win_trades = [p for p in pnls if p > 0]
            loss_trades = [p for p in pnls if p <= 0]

            metrics["win_rate_pct"] = len(win_trades) / len(trades) * 100
            metrics["avg_win"]  = np.mean(win_trades)  if win_trades  else 0.0
            metrics["avg_loss"] = np.mean(loss_trades) if loss_trades else 0.0
            metrics["profit_factor"] = (
                abs(sum(win_trades) / sum(loss_trades))
                if loss_trades and sum(loss_trades) != 0 else float("inf")
            )
            metrics["avg_return_per_trade_pct"] = np.mean(
                [t.return_pct for t in trades]
            )
        else:
            metrics.update({
                "win_rate_pct": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "avg_return_per_trade_pct": 0.0,
            })

        return metrics

    @staticmethod
    def _mdd_duration(drawdown: pd.Series) -> int:
        """計算最大回撤持續天數。"""
        in_drawdown = drawdown < 0
        if not in_drawdown.any():
            return 0

        max_duration = 0
        current_duration = 0
        for v in in_drawdown:
            if v:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_duration

    def format_report(self, metrics: dict, result: "BacktestResult") -> str:
        """格式化績效報告（純文字）。"""
        sep = "─" * 50
        lines = [
            "",
            f"📊 回測報告：{result.symbol} | 策略：{result.strategy_name}",
            f"   期間：{result.start} ~ {result.end}",
            sep,
            "【基本績效】",
            f"  初始資金：    {metrics['initial_capital']:>15,.0f} 元",
            f"  最終資金：    {metrics['final_capital']:>15,.0f} 元",
            f"  總損益：      {metrics['total_pnl']:>+15,.0f} 元",
            f"  總報酬率：    {metrics['total_return_pct']:>+14.2f} %",
            f"  年化報酬率：  {metrics['annualized_return_pct']:>+14.2f} %",
            sep,
            "【風險指標】",
            f"  Sharpe Ratio：{metrics['sharpe_ratio']:>15.3f}",
            f"  最大回撤：    {metrics['max_drawdown_pct']:>+14.2f} %",
            f"  最大回撤期間：{metrics['max_drawdown_duration_days']:>13d} 天",
            f"  Calmar Ratio：{metrics['calmar_ratio']:>15.3f}",
            sep,
            "【交易統計】",
            f"  交易筆數：    {metrics['total_trades']:>15,d}",
            f"  勝率：        {metrics['win_rate_pct']:>14.1f} %",
            f"  平均獲利：    {metrics['avg_win']:>+15,.0f} 元",
            f"  平均虧損：    {metrics['avg_loss']:>+15,.0f} 元",
            f"  獲利因子：    {metrics['profit_factor']:>15.3f}",
            f"  平均每筆報酬：{metrics['avg_return_per_trade_pct']:>+14.2f} %",
            sep,
            "",
        ]
        return "\n".join(lines)
