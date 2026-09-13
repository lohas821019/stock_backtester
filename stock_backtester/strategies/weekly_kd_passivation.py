"""
策略：週 KD 鈍化波段趨勢守護策略（Weekly KD Passivation Strategy - 旗艦多重進場版）

為解決傳統週 KD 指標在強勢大多頭行情（如 2026 年 0050/2330 超級大行情）中：
「超賣買進後在高檔鈍化結束時停利，但後續因行情強勁拉回淺（週 K 未再回到超賣區 25），
導致策略在賣出後徹底空手、錯過數十甚至上百個百分點大波段」的重大痛點。

本策略具備「多重進場機制」與「雙重出場守護機制」：
    - 多重進場機制：
        1. 低檔超跌摸底 (Oversold Dip-Buying)：週 K < oversold_threshold（預設 25.0）。
        2. 低檔金叉轉折 (Low Golden Cross)：週 KD 在低檔區（K < 40）發生黃金交叉。
        3. 高檔鈍化突破 (Passivation Momentum Thrust)：
           當週線 K 向上衝過 80（前週 < 80，本週 >= 80）且週收盤價站穩週均線之上。
           捕捉高檔鈍化啟動之軋空爆發段，讓先前停利出場的資金能順利搭上第二波、第三波主升段！
        4. 多頭均線上金叉中繼 (Mid-Trend Pullback Golden Cross)：
           多頭趨勢中（週收盤價 > 週均線），回檔後 KD 重新黃金交叉。
           徹底解決強勢牛市回檔不深（週 K 只回檔到 50~60）即再度噴出的進場痛點！
    - 雙重出場機制（讓利潤奔馳與防守兼備）：
        1. 鈍化衰竭：週線 K 自 80 上方「向下跌破 80」（K.shift(1) >= 80 且 K < 80），確認高檔強勢動能冷卻。
        2. 趨勢防守破壞：週線收盤跌破週防守均線（預設 10 週均線 MA10）且 K < D 死亡交叉。
    - 防範未來函數（Look-ahead bias）：
        每週五收盤結算週指標與週均線後，訊號自動於次週第一個交易日開盤生效執行。
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class WeeklyKDPassivationStrategy(BaseStrategy):
    """
    週 KD 鈍化波段趨勢守護策略（旗艦多重進場版）。

    參數：
        kd_rsv_window           (int):   週 RSV 週期（週數），預設 9
        kd_k_window             (int):   週 K 平滑週期（週數），預設 3
        kd_d_window             (int):   週 D 平滑週期（週數），預設 3
        oversold_threshold      (float): 超賣買進門檻，預設 25.0
        overbought_threshold    (float): 高檔鈍化門檻，預設 80.0
        exit_ma_period          (int):   週均線出場防守天數（週數），預設 10
        allow_golden_cross      (bool):  是否納入低檔區 KD 金叉進場，預設 True
        allow_passivation_entry (bool):  是否允許「週 K 突破 80 且站上週均線」高檔鈍化動能突破進場，預設 True
        allow_trend_cross       (bool):  是否允許「週線站穩均線之上且 KD 重新金叉」多頭中繼進場，預設 True
    """

    name = "weekly_kd_passivation"
    description = "週 KD 鈍化趨勢守護：低檔超跌+多頭均線上金叉+高檔鈍化突破進場，高檔鈍化抱牢，跌破 80 或週均線出場"

    def __init__(
        self,
        kd_rsv_window: int = 9,
        kd_k_window: int = 3,
        kd_d_window: int = 3,
        oversold_threshold: float = 25.0,
        overbought_threshold: float = 80.0,
        exit_ma_period: int = 10,
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
        """依據週線 KD 鈍化邏輯、均線中繼與多頭突破計算買賣訊號。"""
        min_bars = max(self.kd_rsv_window, self.exit_ma_period) * 5
        if len(data) < min_bars:
            return pd.Series(0, index=data.index, dtype=int)

        # 1. 聚合為週五結算之週線 (W-FRI)
        weekly = data.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

        if len(weekly) < max(self.kd_rsv_window, self.exit_ma_period) + 2:
            return pd.Series(0, index=data.index, dtype=int)

        # 2. 計算週 KD
        k_series, d_series = self._calc_kd(
            high=weekly["high"],
            low=weekly["low"],
            close=weekly["close"],
            rsv_window=self.kd_rsv_window,
            k_window=self.kd_k_window,
            d_window=self.kd_d_window,
        )

        # 3. 計算週防守均線
        ma_series = weekly["close"].rolling(self.exit_ma_period).mean()

        prev_k = k_series.shift(1).fillna(50)
        prev_d = d_series.shift(1).fillna(50)

        # 4. 買進條件：
        #    a) 超跌摸底：週 K < oversold (超賣區買進)
        buy_condition = k_series < self.oversold

        #    b) 低檔金叉轉折：KD 在低檔區 (K < 40) 發生黃金交叉
        if self.allow_golden_cross:
            low_gc = (k_series > d_series) & (prev_k <= prev_d) & (k_series < 40.0)
            buy_condition = buy_condition | low_gc

        #    c) 高檔鈍化突破進場 (Passivation Momentum Thrust)：
        #       當週 K 向上衝破 80 (前週 < 80，本週 >= 80) 且週收盤價高於週均線
        #       抓住主升段高檔鈍化動能，不因前面已停利而錯過再次噴出！
        if self.allow_passivation_entry:
            passivation_breakout = (
                (k_series >= self.overbought)
                & (prev_k < self.overbought)
                & (weekly["close"] > ma_series)
            )
            buy_condition = buy_condition | passivation_breakout

        #    d) 多頭均線金叉中繼 (Mid-Trend Golden Cross)：
        #       多頭趨勢中 (週收盤價 > 週均線)，回檔後 KD 重新形成黃金交叉
        #       在牛市淺幅回檔時果斷再次搭上列車，不遺漏任何波段！
        if self.allow_trend_cross:
            trend_gc = (
                (k_series > d_series)
                & (prev_k <= prev_d)
                & (weekly["close"] > ma_series)
            )
            buy_condition = buy_condition | trend_gc

        # 5. 賣出條件（鈍化衰竭或趨勢破壞）：
        #    a) 鈍化結束：前週 K >= 80，本週向下跌破 80
        fell_below_overbought = (prev_k >= self.overbought) & (k_series < self.overbought)

        #    b) 均線防守破壞：收盤價跌破週防守 MA 且 K < D (死亡交叉)
        break_ma_death_cross = (weekly["close"] < ma_series) & (k_series < d_series)

        sell_condition = fell_below_overbought | break_ma_death_cross

        weekly_signal = pd.Series(0, index=weekly.index, dtype=int)
        weekly_signal[buy_condition] = 1
        weekly_signal[sell_condition] = -1

        # 6. 防範未來函數 (Look-ahead bias)：
        # 週五收盤確認本週狀態，次週第一個交易日生效！
        shifted_weekly_signal = weekly_signal.shift(1).fillna(0)

        # 7. 對齊回日線交易日
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
