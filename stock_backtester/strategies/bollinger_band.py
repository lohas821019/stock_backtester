"""
策略：布林通道突破（Bollinger Band Breakout）

邏輯：
    - 收盤價突破上通道 → 賣出（overbought）
    - 收盤價跌破下通道 → 買進（oversold）
    - 回到中線 → 平倉
"""

import pandas as pd

from .base_strategy import BaseStrategy


class BollingerBandStrategy(BaseStrategy):
    """
    布林通道策略。

    參數：
        window  (int):   布林通道週期，預設 20
        num_std (float): 標準差倍數，預設 2.0
    """

    name = "bollinger_band"
    description = "布林通道策略：跌破下軌買進，突破上軌賣出"

    def __init__(self, window: int = 20, num_std: float = 2.0):
        super().__init__(window=window, num_std=num_std)
        self.window = window
        self.num_std = num_std

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        close = data["close"]

        middle = close.rolling(self.window).mean()
        std    = close.rolling(self.window).std(ddof=0)
        upper  = middle + self.num_std * std
        lower  = middle - self.num_std * std

        signal = pd.Series(0, index=data.index, dtype=int)

        # 跌破下軌：超賣，買進
        signal[close < lower] = 1
        # 突破上軌：超買，賣出
        signal[close > upper] = -1

        return signal
