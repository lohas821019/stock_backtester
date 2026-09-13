"""
策略：雙均線交叉（Moving Average Crossover）

邏輯：
    - 短期均線上穿長期均線 → 買進（黃金交叉）
    - 短期均線下穿長期均線 → 賣出（死亡交叉）
"""

import pandas as pd

from .base_strategy import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """
    雙均線交叉策略。

    參數：
        short_window (int): 短期均線週期，預設 5
        long_window  (int): 長期均線週期，預設 20
        ma_type      (str): 均線類型，"sma"（簡單移動平均）或 "ema"（指數移動平均），預設 "sma"
    """

    name = "ma_cross"
    description = "雙均線交叉策略：短線上穿長線買進，下穿賣出"

    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        ma_type: str = "sma",
    ):
        super().__init__(
            short_window=short_window,
            long_window=long_window,
            ma_type=ma_type,
        )
        self.short_window = short_window
        self.long_window = long_window
        self.ma_type = ma_type.lower()

        if self.short_window >= self.long_window:
            raise ValueError(
                f"short_window ({short_window}) 必須小於 long_window ({long_window})"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        close = data["close"]

        if self.ma_type == "ema":
            short_ma = close.ewm(span=self.short_window, adjust=False).mean()
            long_ma  = close.ewm(span=self.long_window, adjust=False).mean()
        else:  # sma
            short_ma = close.rolling(self.short_window).mean()
            long_ma  = close.rolling(self.long_window).mean()

        signal = pd.Series(0, index=data.index, dtype=int)

        # 黃金交叉：短線從下方穿越上方 → 買進
        golden_cross = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
        # 死亡交叉：短線從上方穿越下方 → 賣出
        death_cross  = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))

        signal[golden_cross] = 1
        signal[death_cross]  = -1

        return signal
