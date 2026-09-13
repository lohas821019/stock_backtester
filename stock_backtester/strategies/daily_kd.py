"""
策略：日 KD 超買超賣策略（Daily KD Strategy）

邏輯：
    - 日線 KD 計算：RSV 週期預設 9，K 週期預設 3，D 週期預設 3
    - 買進條件：日線 K < oversold_threshold（預設 20.0）
    - 賣出條件：日線 K > overbought_threshold（預設 80.0）
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class DailyKDStrategy(BaseStrategy):
    """
    日 KD 超買超賣策略。

    參數：
        kd_rsv_window       (int):   RSV 計算天數，預設 9
        kd_k_window         (int):   K 值平滑天數，預設 3
        kd_d_window         (int):   D 值平滑天數，預設 3
        oversold_threshold  (float): 超賣門檻（低於此值買進），預設 20.0
        overbought_threshold(float): 超買門檻（高於此值賣出），預設 80.0
    """

    name = "daily_kd"
    description = "日 KD 策略：日線 K < 20 買進，K > 80 賣出"

    def __init__(
        self,
        kd_rsv_window: int = 9,
        kd_k_window: int = 3,
        kd_d_window: int = 3,
        oversold_threshold: float = 20.0,
        overbought_threshold: float = 80.0,
    ):
        super().__init__(
            kd_rsv_window=kd_rsv_window,
            kd_k_window=kd_k_window,
            kd_d_window=kd_d_window,
            oversold_threshold=oversold_threshold,
            overbought_threshold=overbought_threshold,
        )
        self.kd_rsv_window = int(kd_rsv_window)
        self.kd_k_window = int(kd_k_window)
        self.kd_d_window = int(kd_d_window)
        self.oversold_threshold = float(oversold_threshold)
        self.overbought_threshold = float(overbought_threshold)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """依據日線 KD 計算買賣訊號。"""
        if len(data) < self.kd_rsv_window:
            return pd.Series(0, index=data.index, dtype=int)

        k_series, d_series = self._calc_kd(
            high=data["high"],
            low=data["low"],
            close=data["close"],
            rsv_window=self.kd_rsv_window,
            k_window=self.kd_k_window,
            d_window=self.kd_d_window,
        )

        signal = pd.Series(0, index=data.index, dtype=int)
        buy_condition = k_series < self.oversold_threshold
        sell_condition = k_series > self.overbought_threshold

        signal[buy_condition] = 1
        signal[sell_condition] = -1

        return signal

    @staticmethod
    def _calc_kd(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        rsv_window: int = 9,
        k_window: int = 3,
        d_window: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        """計算 KD 指標（台股標準平滑演算法）。"""
        lowest_low = low.rolling(rsv_window).min()
        highest_high = high.rolling(rsv_window).max()

        denom = (highest_high - lowest_low).replace(0, np.nan)
        rsv = ((close - lowest_low) / denom * 100).fillna(50)

        k = pd.Series(50.0, index=close.index)
        d = pd.Series(50.0, index=close.index)

        alpha_k = 1.0 / k_window
        alpha_d = 1.0 / d_window

        k_val = 50.0
        d_val = 50.0

        for i in range(len(close)):
            cur_rsv = rsv.iloc[i]
            if not np.isnan(cur_rsv):
                k_val = (1 - alpha_k) * k_val + alpha_k * cur_rsv
                d_val = (1 - alpha_d) * d_val + alpha_d * k_val
            k.iloc[i] = k_val
            d.iloc[i] = d_val

        return k, d
