"""
策略：週 RSI 鈍化波段趨勢守護策略（Weekly RSI Passivation Strategy）

針對傳統 RSI 指標在強勢大多頭時「RSI > 70 過早停利（賣飛）」的痛點進行量化優化：
    - 多重進場機制：
        1. 低檔超跌摸底 (Oversold Rebound)：週 RSI < oversold（預設 35.0）。
        2. 多頭中繼突破 (Mid-line 50 Breakout)：週 RSI 向上突破 50 中軸線且週收盤價站穩週防守均線（預設 10 週 MA10）。
        3. 高檔鈍化動能突破 (Passivation Thrust)：
           當週 RSI 向上衝破 70（前週 < 70，當週 >= 70）且週收盤價站穩週均線。
           高檔超買不再是恐慌賣點，而是強勢軋空主升段啟動！
    - 雙重出場機制（保護利潤與防守）：
        1. 鈍化衰竭：週 RSI 自 70 高檔向下跌破 70，強勢動能冷卻停利。
        2. 趨勢破壞防守：週收盤價跌破週防守 MA 且 RSI < 50。
    - 防範未來函數（Look-ahead bias）：
        每週五收盤結算週指標與週均線後，訊號自動於次週第一個交易日開盤生效執行。
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class WeeklyRSIStrategy(BaseStrategy):
    """
    週 RSI 鈍化波段守護策略。

    參數：
        period                  (int):   週 RSI 計算週期（週數），預設 14
        oversold                (float): 超賣買進門檻，預設 35.0
        overbought              (float): 高檔鈍化門檻，預設 70.0
        exit_ma_period          (int):   週均線防守週期（週數），預設 10
        allow_mid_cross         (bool):  是否允許週 RSI 突破 50 中軸且站穩均線多頭中繼進場，預設 True
        allow_passivation_entry (bool):  是否允許週 RSI 衝過 70 高檔鈍化動能突破進場，預設 True
    """

    name = "weekly_rsi"
    description = "週 RSI 鈍化趨勢守護：超跌低接+50中軸金叉+70高檔鈍化突破進場，跌破 70 或週均線出場"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 35.0,
        overbought: float = 70.0,
        exit_ma_period: int = 10,
        allow_mid_cross: bool = True,
        allow_passivation_entry: bool = True,
    ):
        super().__init__(
            period=period,
            oversold=oversold,
            overbought=overbought,
            exit_ma_period=exit_ma_period,
            allow_mid_cross=allow_mid_cross,
            allow_passivation_entry=allow_passivation_entry,
        )
        self.period = int(period)
        self.oversold = float(oversold)
        self.overbought = float(overbought)
        self.exit_ma_period = int(exit_ma_period)
        self.allow_mid_cross = bool(allow_mid_cross)
        self.allow_passivation_entry = bool(allow_passivation_entry)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """依據週線 RSI 鈍化邏輯與週均線計算買賣訊號。"""
        min_bars = max(self.period, self.exit_ma_period) * 5
        if len(data) < min_bars:
            return pd.Series(0, index=data.index, dtype=int)

        # 1. 將日線 Resample 為週線 (W-FRI)
        weekly = data.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(weekly) < max(self.period, self.exit_ma_period) + 2:
            return pd.Series(0, index=data.index, dtype=int)

        # 2. 計算週 RSI 與週防守均線
        rsi_series = self._calc_rsi(weekly["close"], period=self.period)
        ma_series = weekly["close"].rolling(self.exit_ma_period).mean()

        prev_rsi = rsi_series.shift(1).fillna(50)

        # 3. 買進條件：
        #    a) 超跌摸底：週 RSI < oversold
        buy_condition = rsi_series < self.oversold

        #    b) 多頭中繼突破：週 RSI 突破 50 中軸線且收盤價 > 週均線
        if self.allow_mid_cross:
            mid_cross = (
                (rsi_series >= 50.0)
                & (prev_rsi < 50.0)
                & (weekly["close"] > ma_series)
            )
            buy_condition = buy_condition | mid_cross

        #    c) 高檔鈍化動能突破：週 RSI 衝過 70 (強勢軋空主升浪) 且收盤價 > 週均線
        if self.allow_passivation_entry:
            passivation_breakout = (
                (rsi_series >= self.overbought)
                & (prev_rsi < self.overbought)
                & (weekly["close"] > ma_series)
            )
            buy_condition = buy_condition | passivation_breakout

        # 4. 賣出條件：
        #    a) 鈍化結束：週 RSI 自 70 以上向下跌破 70
        fell_below_overbought = (prev_rsi >= self.overbought) & (rsi_series < self.overbought)

        #    b) 均線防守破壞：週收盤價跌破週防守 MA 且 RSI < 50
        break_ma = (weekly["close"] < ma_series) & (rsi_series < 50.0)

        sell_condition = fell_below_overbought | break_ma

        weekly_signal = pd.Series(0, index=weekly.index, dtype=int)
        weekly_signal[buy_condition] = 1
        weekly_signal[sell_condition] = -1

        # 5. 防範未來函數 (Look-ahead bias)：
        # 當週週五收盤確認本週狀態，次週交易日執行！
        shifted_weekly_signal = weekly_signal.shift(1).fillna(0)

        # 6. 重新對齊回日線日期 (使用 week_period 映射)
        weekly_idx = (
            weekly.index.tz_localize(None)
            if hasattr(weekly.index, "tz") and weekly.index.tz is not None
            else weekly.index
        )
        period_to_sig = pd.Series(
            shifted_weekly_signal.values,
            index=weekly_idx.to_period("W-FRI"),
        )
        period_to_sig = period_to_sig[~period_to_sig.index.duplicated(keep="last")]

        data_idx = (
            data.index.tz_localize(None)
            if hasattr(data.index, "tz") and data.index.tz is not None
            else data.index
        )
        daily_periods = data_idx.to_period("W-FRI")
        mapped_vals = daily_periods.map(period_to_sig).fillna(0).astype(int)
        sig = pd.Series(mapped_vals, index=data.index)

        # 只在訊號切換的第一個交易日觸發，避免持倉期間每日重複下單
        result_signal = pd.Series(0, index=data.index, dtype=int)
        result_signal[(sig == 1) & (sig != sig.shift(1).fillna(0))] = 1
        result_signal[(sig == -1) & (sig != sig.shift(1).fillna(0))] = -1

        return result_signal

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI（使用 Wilder 平滑法）。"""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, float("inf"))
        rsi = 100 - (100 / (1 + rs))
        return rsi
