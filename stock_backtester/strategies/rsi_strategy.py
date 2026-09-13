"""
策略：日 RSI 超買超賣策略（Daily RSI Strategy）

邏輯：
    - 日線 RSI 計算（Wilder 平滑法，預設週期 14）
    - RSI < oversold 閾值（預設 30.0）→ 買進
    - RSI > overbought 閾值（預設 70.0）→ 賣出
"""

import pandas as pd

from .base_strategy import BaseStrategy


class DailyRSIStrategy(BaseStrategy):
    """
    日 RSI 超買超賣策略。

    參數：
        period     (int):   日線 RSI 計算週期，預設 14
        oversold   (float): 超賣閾值，低於此值買進，預設 30.0
        overbought (float): 超買閾值，高於此值賣出，預設 70.0
    """

    name = "daily_rsi"
    description = "日 RSI 策略：日線 RSI 超賣買進（< 30），超買賣出（> 70）"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ):
        super().__init__(period=period, oversold=oversold, overbought=overbought)
        self.period = int(period)
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        close = data["close"]
        rsi = self._calc_rsi(close, self.period)

        signal = pd.Series(0, index=data.index, dtype=int)
        signal[rsi < self.oversold] = 1
        signal[rsi > self.overbought] = -1

        return signal

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int) -> pd.Series:
        """計算 RSI（使用 Wilder 平滑法）。"""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, float("inf"))
        rsi = 100 - (100 / (1 + rs))
        return rsi


# 向下相容別名
RSIStrategy = DailyRSIStrategy
