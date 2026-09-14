"""
回測引擎 BacktestEngine

事件驅動式回測：逐日模擬交易，計算資金曲線與績效。

特性：
- 支援買進持有（Long Only）模式
- 手續費與滑價模擬
- 詳細成交記錄
"""

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import numpy as np

from ..strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """單筆成交記錄。"""
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    direction: int  # 1=多, -1=空
    commission: float = 0.0

    @property
    def pnl(self) -> float:
        """損益（扣除手續費）。"""
        gross = (self.exit_price - self.entry_price) * self.shares * self.direction
        return gross - self.commission

    @property
    def return_pct(self) -> float:
        """報酬率（%）。"""
        return (self.exit_price / self.entry_price - 1) * self.direction * 100


@dataclass
class BacktestResult:
    """回測結果。"""
    symbol: str
    strategy_name: str
    start: date
    end: date

    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    signals: pd.Series = field(default_factory=pd.Series)
    raw_signals: pd.Series = field(default_factory=pd.Series)
    data: pd.DataFrame = field(default_factory=pd.DataFrame)

    initial_capital: float = 1_000_000.0
    final_capital: float = 0.0


class BacktestEngine:
    """
    回測引擎。

    使用範例：
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, strategy, symbol="2330")
        print(result.equity_curve)
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        commission_rate: float = 0.001425,   # 買進手續費 0.1425%
        tax_rate: float = 0.003,             # 賣出交易稅 0.3%
        slippage: float = 0.001,             # 滑價 0.1%
        position_size: float = 0.95,         # 每次投入資金比例
        allow_odd_lots: bool = True,         # 支援零股（依資金精確配置股數，避免千元高價股買不起整張問題）
    ):
        """
        Args:
            initial_capital: 初始資金（元）
            commission_rate: 買進手續費率（台股 0.1425%）
            tax_rate:        賣出交易稅率（台股 0.3%）
            slippage:        滑價比率
            position_size:   每次進場投入比例（0~1）
            allow_odd_lots:  是否支援零股配置（預設 True）
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.slippage = slippage
        self.position_size = position_size
        self.allow_odd_lots = allow_odd_lots

    def run(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy,
        symbol: str = "",
    ) -> BacktestResult:
        """
        執行回測。

        Args:
            data:     標準 OHLCV DataFrame（DatetimeIndex，升序）
            strategy: 策略實例
            symbol:   股票代號（僅用於報告）

        Returns:
            BacktestResult
        """
        if data.empty:
            raise ValueError("data 不能為空")

        # 防禦性清洗：確保進入回測引擎之數據不包含任何 NaN 或無效價格列
        data = data.dropna(subset=["open", "high", "low", "close"]).copy()
        data = data[(data["open"] > 0) & (data["close"] > 0)]
        if data.empty:
            raise ValueError("有效價格資料為空")

        signals = strategy.generate_signals(data)
        result = BacktestResult(
            symbol=symbol,
            strategy_name=strategy.name,
            start=data.index[0].date(),
            end=data.index[-1].date(),
            signals=signals,
            data=data,
            initial_capital=self.initial_capital,
        )

        capital = self.initial_capital
        position = 0      # 持有股數
        entry_price = 0.0
        entry_date = None
        equity_values = []

        for i, (dt, row) in enumerate(data.iterrows()):
            sig = signals.iloc[i] if i < len(signals) else 0
            close = row["close"]
            # 模擬以次日開盤價（或收盤價）成交
            exec_price = close * (1 + self.slippage if sig == 1 else 1 - self.slippage)

            # 買進訊號 & 空倉
            if sig == 1 and position == 0:
                invest = capital * self.position_size
                if self.allow_odd_lots:
                    shares = int(invest / exec_price)
                else:
                    lots = int(invest / (exec_price * 1000))
                    shares = lots * 1000

                if shares > 0:
                    buy_commission = exec_price * shares * self.commission_rate
                    total_cost = exec_price * shares + buy_commission

                    if total_cost <= capital:
                        capital -= total_cost
                        position = shares
                        entry_price = exec_price
                        entry_date = dt
                        logger.debug(
                            "[Engine] %s 買進 %d 股 @ %.2f", dt.date(), shares, exec_price
                        )

            # 賣出訊號 & 持有部位
            elif sig == -1 and position > 0:
                sell_commission = exec_price * position * self.commission_rate
                sell_tax = exec_price * position * self.tax_rate
                proceeds = exec_price * position - sell_commission - sell_tax

                trade = Trade(
                    entry_date=entry_date,
                    exit_date=dt,
                    entry_price=entry_price,
                    exit_price=exec_price,
                    shares=position,
                    direction=1,
                    commission=sell_commission + sell_tax,
                )
                result.trades.append(trade)

                capital += proceeds
                logger.debug(
                    "[Engine] %s 賣出 %d 股 @ %.2f，損益 %.0f",
                    dt.date(), position, exec_price, trade.pnl,
                )
                position = 0
                entry_price = 0.0
                entry_date = None

            # 計算當日總資產（現金 + 持倉市值）
            total_equity = capital + position * close
            equity_values.append(total_equity)

        # 若回測結束仍有持倉，強制平倉結算
        if position > 0:
            last_close = data["close"].iloc[-1]
            sell_commission = last_close * position * self.commission_rate
            sell_tax = last_close * position * self.tax_rate
            proceeds = last_close * position - sell_commission - sell_tax
            trade = Trade(
                entry_date=entry_date,
                exit_date=data.index[-1],
                entry_price=entry_price,
                exit_price=last_close,
                shares=position,
                direction=1,
                commission=sell_commission + sell_tax,
            )
            result.trades.append(trade)
            capital += proceeds
            if equity_values:
                equity_values[-1] = capital

        # 產生實際成交的訊號（1: 買進進場, -1: 賣出出場），確保訊號與交易記錄 100% 嚴格成對對應
        executed_signals = pd.Series(0, index=data.index, dtype=int)
        for trade in result.trades:
            executed_signals.loc[trade.entry_date] = 1
            executed_signals.loc[trade.exit_date] = -1

        result.raw_signals = signals
        result.signals = executed_signals
        result.final_capital = capital
        result.equity_curve = pd.Series(equity_values, index=data.index)

        logger.info(
            "[Engine] 回測完成: %s | %d 筆交易 | 最終資金 %.0f",
            strategy.name, len(result.trades), capital,
        )

        return result
