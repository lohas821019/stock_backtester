"""
策略：月 KD 鈍化波段趨勢守護策略（Monthly KD Passivation Strategy）

仿照週 KD 鈍化策略設計，提升至超大長線「月線（Monthly）」層級：
    - 長線波段核心優勢：
        月線是法人主力、退休基金、大戶的核心佈局週期，雜訊極少、單一主升浪往往長達數月至數年。
    - 多重進場機制：
        1. 低檔超跌摸底 (Oversold Dip-Buying)：月 K < oversold_threshold（預設 30.0）。
        2. 低檔金叉轉折 (Low Golden Cross)：月 KD 在低檔區（K < 45）發生黃金交叉。
        3. 高檔鈍化突破進場 (Passivation Momentum Thrust)：
           當月線 K 衝過 80（前月 < 80，當月 >= 80）且月收盤價站穩月防守均線（預設 6 個月 MA6）。
           大行情展開時，月線高檔鈍化是威力最強的超級大主升浪，堅決做多！
        4. 多頭均線上金叉中繼 (Mid-Trend Golden Cross)：
           多頭趨勢中（月收盤價 > 月均線），回檔後月 KD 重新金叉，果斷再次上車。
    - 雙重出場機制（保護利潤與防守）：
        1. 鈍化衰竭：月線 K 自 80 上方向下跌破 80，動能降溫停利。
        2. 趨勢破壞防守：月收盤價跌破月均線（MA6）且 K < D 死亡交叉出場。
    - 防範未來函數（Look-ahead bias）：
        每月底收盤結算月指標與月均線後，訊號自動於次月第一個交易日開盤生效執行。
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class MonthlyKDPassivationStrategy(BaseStrategy):
    """
    月 KD 鈍化長線波段守護策略。

    參數：
        kd_rsv_window           (int):   月 RSV 週期（月數），預設 9
        kd_k_window             (int):   月 K 平滑週期（月數），預設 3
        kd_d_window             (int):   月 D 平滑週期（月數），預設 3
        oversold_threshold      (float): 超賣買進門檻，預設 30.0
        overbought_threshold    (float): 高檔鈍化門檻，預設 80.0
        exit_ma_period          (int):   月均線防守週期（月數），預設 6 (半年線)
        allow_golden_cross      (bool):  是否納入低檔區 KD 金叉進場，預設 True
        allow_passivation_entry (bool):  是否允許「月 K 突破 80 且站上月均線」高檔鈍化動能突破進場，預設 True
        allow_trend_cross       (bool):  是否允許「月線站穩均線之上且 KD 重新金叉」多頭中繼進場，預設 True
    """

    name = "monthly_kd_passivation"
    description = "月 KD 鈍化趨勢守護：大長線超跌+均線上金叉+高檔鈍化突破進場，跌破 80 或月均線出場"

    def __init__(
        self,
        kd_rsv_window: int = 9,
        kd_k_window: int = 3,
        kd_d_window: int = 3,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 80.0,
        exit_ma_period: int = 6,
        allow_golden_cross: bool = True,
        allow_passivation_entry: bool = True,
        allow_trend_cross: bool = True,
    ):
        super().__init__(
            kd_rsv_window=kd_rsv_window,
            kd_k_window=kd_k_window,
            kd_d_window=kd_d_window,
            oversold_threshold=oversold_threshold,
            overbought_threshold=overbought_threshold,
            exit_ma_period=exit_ma_period,
            allow_golden_cross=allow_golden_cross,
            allow_passivation_entry=allow_passivation_entry,
            allow_trend_cross=allow_trend_cross,
        )
        self.kd_rsv_window = int(kd_rsv_window)
        self.kd_k_window = int(kd_k_window)
        self.kd_d_window = int(kd_d_window)
        self.oversold = float(oversold_threshold)
        self.overbought = float(overbought_threshold)
        self.exit_ma_period = int(exit_ma_period)
        self.allow_golden_cross = bool(allow_golden_cross)
        self.allow_passivation_entry = bool(allow_passivation_entry)
        self.allow_trend_cross = bool(allow_trend_cross)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """依據月線 KD 鈍化邏輯、月均線中繼與多頭突破計算買賣訊號。"""
        min_bars = max(self.kd_rsv_window, self.exit_ma_period) * 20
        if len(data) < min_bars:
            return pd.Series(0, index=data.index, dtype=int)

        # 1. 聚合為每月底結算之月線 (ME)
        monthly = data.resample("ME").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(monthly) < max(self.kd_rsv_window, self.exit_ma_period) + 2:
            return pd.Series(0, index=data.index, dtype=int)

        # 2. 計算月 KD
        k_series, d_series = self._calc_kd(
            high=monthly["high"],
            low=monthly["low"],
            close=monthly["close"],
            rsv_window=self.kd_rsv_window,
            k_window=self.kd_k_window,
            d_window=self.kd_d_window,
        )

        # 3. 計算月防守均線
        ma_series = monthly["close"].rolling(self.exit_ma_period).mean()

        prev_k = k_series.shift(1).fillna(50)
        prev_d = d_series.shift(1).fillna(50)

        # 4. 買進條件：
        #    a) 超跌摸底：月 K < oversold (預設 30.0)
        buy_condition = k_series < self.oversold

        #    b) 低檔金叉轉折：月 KD 在低檔區 (K < 45) 發生黃金交叉
        if self.allow_golden_cross:
            low_gc = (k_series > d_series) & (prev_k <= prev_d) & (k_series < 45.0)
            buy_condition = buy_condition | low_gc

        #    c) 高檔鈍化突破進場 (Passivation Momentum Thrust)：
        #       當月 K 衝過 80 (前月 < 80，本月 >= 80) 且月收盤價高於月均線
        if self.allow_passivation_entry:
            passivation_breakout = (
                (k_series >= self.overbought)
                & (prev_k < self.overbought)
                & (monthly["close"] > ma_series)
            )
            buy_condition = buy_condition | passivation_breakout

        #    d) 多頭均線金叉中繼 (Mid-Trend Golden Cross)：
        #       多頭趨勢中 (月收盤價 > 月均線)，回檔後 KD 重新形成黃金交叉
        if self.allow_trend_cross:
            trend_gc = (
                (k_series > d_series)
                & (prev_k <= prev_d)
                & (monthly["close"] > ma_series)
            )
            buy_condition = buy_condition | trend_gc

        # 5. 賣出條件（鈍化衰竭或趨勢破壞）：
        #    a) 鈍化結束：前月 K >= 80，本月向下跌破 80
        fell_below_overbought = (prev_k >= self.overbought) & (k_series < self.overbought)

        #    b) 均線防守破壞：收盤價跌破月防守 MA 且 K < D (死亡交叉)
        break_ma_death_cross = (monthly["close"] < ma_series) & (k_series < d_series)

        sell_condition = fell_below_overbought | break_ma_death_cross

        monthly_signal = pd.Series(0, index=monthly.index, dtype=int)
        monthly_signal[buy_condition] = 1
        monthly_signal[sell_condition] = -1

        # 6. 防範未來函數 (Look-ahead bias)：
        # 每月底收盤確認當月狀態，次月第一個交易日生效！
        shifted_monthly_signal = monthly_signal.shift(1).fillna(0)

        # 7. 對齊回日線交易日
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
