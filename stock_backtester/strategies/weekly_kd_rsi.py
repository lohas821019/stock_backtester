"""
策略：週 KD 與 週 RSI 極端超跌超買共振策略 (Weekly KD & Weekly RSI Reversal Strategy)

邏輯說明：
    利用日線資料 Resample 成週 K 線（以每週最後一個交易日為基準），
    計算中長線的「週 KD」與「週 RSI」技術指標：
    - 買進訊號（入場點）：
      週 KD 與 週 RSI 同時小於 20（極端超跌共振，底部承接起漲點）
    - 賣出訊號（出場點）：
      週 KD 與 週 RSI 同時大於 90（極端超買共振，高檔全面獲利了結）

防範未來函數 (No Look-ahead Bias)：
    當週的週線指標必須等到當週最後一個交易日收盤才能確定，
    因此計算出週訊號後會向後 shift 一期（次週首個交易日生效），再映射回日線。
"""

import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy


class WeeklyKdRsiStrategy(BaseStrategy):
    """
    週 KD 與 週 RSI 極端值雙重共振策略。

    參數：
        kd_rsv_window       (int):   KD 的 RSV 計算週期（週數），預設 9
        kd_k_window         (int):   K 值的平滑週期，預設 3
        kd_d_window         (int):   D 值的平滑週期，預設 3
        rsi_window          (int):   週 RSI 計算週期（週數），預設 14
        oversold_threshold  (float): 買進閾值（週 KD 與 週 RSI 同時小於此值），預設 20.0
        overbought_threshold(float): 賣出閾值（週 KD 與 週 RSI 同時大於此值），預設 90.0
    """

    name = "weekly_kd_rsi"
    description = "週 KD 與 週 RSI 同時小於 20 買進，兩者同時大於 90 賣出"

    def __init__(
        self,
        kd_rsv_window: int = 9,
        kd_k_window: int = 3,
        kd_d_window: int = 3,
        rsi_window: int = 14,
        oversold_threshold: float = 20.0,
        overbought_threshold: float = 90.0,
    ):
        super().__init__(
            kd_rsv_window=kd_rsv_window,
            kd_k_window=kd_k_window,
            kd_d_window=kd_d_window,
            rsi_window=rsi_window,
            oversold_threshold=oversold_threshold,
            overbought_threshold=overbought_threshold,
        )
        self.kd_rsv_window = int(kd_rsv_window)
        self.kd_k_window = int(kd_k_window)
        self.kd_d_window = int(kd_d_window)
        self.rsi_window = int(rsi_window)
        self.oversold_threshold = float(oversold_threshold)
        self.overbought_threshold = float(overbought_threshold)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if len(data) < self.kd_rsv_window * 5:
            return pd.Series(0, index=data.index, dtype=int)

        # 1. 將日線 Resample 為週線 (W-FRI: 以每週最後一個交易日結算)
        weekly = data.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(weekly) < max(self.kd_rsv_window, self.rsi_window) + 2:
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

        # 3. 計算週 RSI
        rsi_series = self._calc_rsi(weekly["close"], period=self.rsi_window)

        # 4. 計算週訊號
        weekly_signal = pd.Series(0, index=weekly.index, dtype=int)

        # 買進條件：週 KD < 20 且 週 RSI < 20（同時成立）
        # 判定：K < 20 (或 K, D 均小於 20) 且 RSI < 20
        buy_condition = (k_series < self.oversold_threshold) & (rsi_series < self.oversold_threshold)

        # 賣出條件：週 KD > 90 且 週 RSI > 90（同時成立）
        sell_condition = (k_series > self.overbought_threshold) & (rsi_series > self.overbought_threshold)

        weekly_signal[buy_condition] = 1
        weekly_signal[sell_condition] = -1

        # 5. 防範未來函數 (Look-ahead bias)：
        # 當週週五收盤後才能確認本週訊號，因此 shift(1) 週，次週交易日才執行！
        shifted_weekly_signal = weekly_signal.shift(1).fillna(0)

        # 6. 重新對齊回日線日期 (使用 week_period 映射)
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
        high: pd.Series, low: pd.Series, close: pd.Series,
        rsv_window: int = 9, k_window: int = 3, d_window: int = 3
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

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI（Wilder 平滑法）。"""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, float("inf"))
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
