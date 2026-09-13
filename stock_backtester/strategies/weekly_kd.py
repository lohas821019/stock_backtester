"""
策略：週 KD 超買超賣策略（Weekly KD Strategy）

邏輯：
    - 週線 KD 計算：將日線資料重採樣為每週週五結算之週線（W-FRI）
    - 週線 RSV 週期預設 9 週，K 週期預設 3 週，D 週期預設 3 週
    - 買進條件：週線 K < oversold_threshold（預設 20.0）
    - 賣出條件：週線 K > overbought_threshold（預設 80.0）
    - 防範未來函數（Look-ahead bias）：週五收盤結算週指標後，訊號於次週第一個交易日開盤生效執行。
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class WeeklyKDStrategy(BaseStrategy):
    """
    週 KD 超買超賣策略。

    參數：
        kd_rsv_window       (int):   週 RSV 計算週期（週數），預設 9
        kd_k_window         (int):   週 K 值平滑週期（週數），預設 3
        kd_d_window         (int):   週 D 值平滑週期（週數），預設 3
        oversold_threshold  (float): 超賣門檻（低於此值買進），預設 20.0
        overbought_threshold(float): 超買門檻（高於此值賣出），預設 80.0
    """

    name = "weekly_kd"
    description = "週 KD 策略：週線 K < 20 買進，K > 80 賣出"

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
        """依據週線 KD 計算買賣訊號並對齊回日線交易日。"""
        if len(data) < self.kd_rsv_window * 5:
            return pd.Series(0, index=data.index, dtype=int)

        # 1. 將日線 Resample 為週線 (W-FRI: 以每週五或最後交易日結算)
        weekly = data.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(weekly) < self.kd_rsv_window + 2:
            return pd.Series(0, index=data.index, dtype=int)

        # 2. 計算週 KD (K值, D值)
        k_series, d_series = self._calc_kd(
            high=weekly["high"],
            low=weekly["low"],
            close=weekly["close"],
            rsv_window=self.kd_rsv_window,
            k_window=self.kd_k_window,
            d_window=self.kd_d_window,
        )

        # 3. 計算週訊號
        weekly_signal = pd.Series(0, index=weekly.index, dtype=int)
        buy_condition = k_series < self.oversold_threshold
        sell_condition = k_series > self.overbought_threshold

        weekly_signal[buy_condition] = 1
        weekly_signal[sell_condition] = -1

        # 4. 防範未來函數 (Look-ahead bias)：
        # 當週週五收盤後才能確認本週訊號，因此 shift(1) 週，次週交易日才執行！
        shifted_weekly_signal = weekly_signal.shift(1).fillna(0)

        # 5. 重新對齊回日線日期 (使用 week_period 映射)
        weekly_idx = weekly.index.tz_localize(None) if hasattr(weekly.index, "tz") and weekly.index.tz is not None else weekly.index
        period_to_sig = pd.Series(
            shifted_weekly_signal.values,
            index=weekly_idx.to_period("W-FRI")
        )
        period_to_sig = period_to_sig[~period_to_sig.index.duplicated(keep="last")]

        data_idx = data.index.tz_localize(None) if hasattr(data.index, "tz") and data.index.tz is not None else data.index
        daily_periods = data_idx.to_period("W-FRI")
        sig = daily_periods.map(period_to_sig).fillna(0).astype(int)
        sig = pd.Series(sig.values, index=data.index)

        # 只在訊號切換的第一個交易日觸發，避免持倉期間每日重複下單
        result_signal = pd.Series(0, index=data.index, dtype=int)
        result_signal[(sig == 1) & (sig != sig.shift(1).fillna(0))] = 1
        result_signal[(sig == -1) & (sig != sig.shift(1).fillna(0))] = -1

        return result_signal

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
