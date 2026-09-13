"""
策略：月 RSI 鈍化波段趨勢守護策略（Monthly RSI Strategy）

仿照鈍化守護哲學，提升至超大長線「月線（Monthly）」層級：
    - 傳統 RSI 在強多頭市場「超買即賣（>70 賣出）」的巨大缺點：
        在大多頭單邊噴出行情中，月 RSI 往往衝破 70 進入強勢鈍化（如 2023~2026 台積電、0050），
        若一到 70 就急著賣出，會錯過後續翻倍的大牛市！
    - 多重進場機制：
        1. 低檔超賣回升 (Oversold Rebound)：月 RSI < oversold（預設 40.0）。
        2. 多頭中繼突破 (Mid-line 50 Breakout)：月 RSI 向上突破 50 中軸線且月收盤價站穩月均線（預設 6 個月 MA6）。
        3. 高檔鈍化動能突破 (Passivation Thrust)：
           當月 RSI 向上衝破 70（前月 < 70，當月 >= 70）且月收盤價高於月均線。
           高檔鈍化確立強勢動能爆發，強勢做多！
    - 雙重出場機制（保護利潤與防守）：
        1. 鈍化衰竭：月 RSI 自 70 高檔向下跌破 70，強勢動能降溫停利。
        2. 趨勢轉空防守：月收盤價跌破月防守 MA 且 RSI < 50。
    - 防範未來函數（Look-ahead bias）：
        每月底收盤結算月指標後，訊號自動於次月第一個交易日開盤生效執行。
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class MonthlyRSIStrategy(BaseStrategy):
    """
    月 RSI 鈍化波段守護策略。

    參數：
        period                  (int):   月 RSI 計算週期（月數），預設 14
        oversold                (float): 超賣門檻，預設 40.0
        overbought              (float): 高檔鈍化門檻，預設 70.0
        exit_ma_period          (int):   月均線防守週期（月數），預設 6 (半年線)
        allow_mid_cross         (bool):  是否允許月 RSI 突破 50 中軸且站穩均線多頭中繼進場，預設 True
        allow_passivation_entry (bool):  是否允許月 RSI 衝過 70 高檔鈍化動能突破進場，預設 True
    """

    name = "monthly_rsi"
    description = "月 RSI 鈍化趨勢守護：大長線超跌+50中軸金叉+70高檔鈍化突破進場，跌破 70 或月均線出場"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 40.0,
        overbought: float = 70.0,
        exit_ma_period: int = 6,
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
        """依據月線 RSI 鈍化與月均線計算買賣訊號並對齊日線。"""
        min_bars = max(self.period, self.exit_ma_period) * 20
        if len(data) < min_bars:
            return pd.Series(0, index=data.index, dtype=int)

        # 1. 聚合為月線 (ME)
        monthly = data.resample("ME").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(monthly) < max(self.period, self.exit_ma_period) + 2:
            return pd.Series(0, index=data.index, dtype=int)

        # 2. 計算月 RSI 與防守均線
        rsi_series = self._calc_rsi(monthly["close"], period=self.period)
        ma_series = monthly["close"].rolling(self.exit_ma_period).mean()

        prev_rsi = rsi_series.shift(1).fillna(50)

        # 3. 買進條件：
        #    a) 超跌摸底：月 RSI < oversold
        buy_condition = rsi_series < self.oversold

        #    b) 多頭中繼突破：月 RSI 突破 50 中軸線且收盤價 > 月均線
        if self.allow_mid_cross:
            mid_cross = (
                (rsi_series >= 50.0)
                & (prev_rsi < 50.0)
                & (monthly["close"] > ma_series)
            )
            buy_condition = buy_condition | mid_cross

        #    c) 高檔鈍化動能突破：月 RSI 衝過 70 (強勢軋空主升浪) 且收盤價 > 月均線
        if self.allow_passivation_entry:
            passivation_breakout = (
                (rsi_series >= self.overbought)
                & (prev_rsi < self.overbought)
                & (monthly["close"] > ma_series)
            )
            buy_condition = buy_condition | passivation_breakout

        # 4. 賣出條件：
        #    a) 鈍化結束：月 RSI 自 70 以上向下跌破 70
        fell_below_overbought = (prev_rsi >= self.overbought) & (rsi_series < self.overbought)

        #    b) 均線防守破壞：月收盤價跌破月防守 MA 且 RSI < 50
        break_ma = (monthly["close"] < ma_series) & (rsi_series < 50.0)

        sell_condition = fell_below_overbought | break_ma

        monthly_signal = pd.Series(0, index=monthly.index, dtype=int)
        monthly_signal[buy_condition] = 1
        monthly_signal[sell_condition] = -1

        # 5. 防範未來函數 (Look-ahead bias)：
        # 當月收盤確認後，次月第一個交易日生效！
        shifted_monthly_signal = monthly_signal.shift(1).fillna(0)

        # 6. 重新對齊回日線交易日
        monthly_idx = (
            monthly.index.tz_localize(None)
            if hasattr(monthly.index, "tz") and monthly.index.tz is not None
            else monthly.index
        )
        period_to_sig = pd.Series(
            shifted_monthly_signal.values,
            index=monthly_idx.to_period("M"),
        )
        period_to_sig = period_to_sig[~period_to_sig.index.duplicated(keep="last")]

        data_idx = (
            data.index.tz_localize(None)
            if hasattr(data.index, "tz") and data.index.tz is not None
            else data.index
        )
        daily_periods = data_idx.to_period("M")
        mapped_vals = daily_periods.map(period_to_sig).fillna(0).astype(int)
        sig = pd.Series(mapped_vals, index=data.index)

        # 只在訊號切換的第一個交易日觸發
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
