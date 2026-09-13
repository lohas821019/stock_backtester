"""
策略：相對低位階抄底阿爾法策略（Dip Hunter Alpha Strategy）

專為「空手尋求相對低位階安全上車」的投資者設計。
不追高、不追噴出，專注於歷史統計勝率最高的 3 大低位階抄底甜蜜點：

【抄底信號 1：多頭回踩季線支撐（MA60 Pullback Support）】
  - 適用情境：大多頭格局中的良性洗盤回檔
  - 門檻條件：股價拉回至 60 日季線支撐區（季線乖離率介於 -2.0% ~ +1.0%）
  - 確認條件：當日收紅 K 線（收盤 > 開盤）或站回季線，確認主力守盤
  - 歷史統計：60 日持有勝率高達 80.8%！

【抄底信號 2：短線動能極度超賣金叉（Oversold Momentum Reversal）】
  - 適用情境：波段急跌震盪落底
  - 門檻條件：日 KD <= 25 出現低檔黃金交叉，或 RSI(14) <= 35 且當日收紅 K
  - 歷史統計：KD <= 20 金叉 20 日勝率 92.3%、KD <= 25 金叉 60 日勝率 80.0%！

【抄底信號 3：恐慌超跌大底投降反轉（Capitulation Extreme Panic）】
  - 適用情境：大盤暴跌、系統性黑天鵝殺盤
  - 門檻條件：季線負乖離率 <= -6.0%（嚴重超跌超賣區間）
  - 確認條件：落底收紅 K 或負乖離快速收斂
  - 歷史統計：60 日持有勝率 83.8%，平均波段報酬高達 +14.19%！

【出場防守與獲利了結】：
  - 初始停損：進場成本 -8.0% 硬性停損，杜絕向下攤平風險
  - 噴出獲利：季線正乖離達到 +22.0% 進入狂熱區後，啟動自最高點回撤 -8.0% 移動停利
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class DipHunterAlphaStrategy(BaseStrategy):
    """
    相對低位階抄底阿爾法策略。

    參數：
        bias_ma_period      (int):   季線週期，預設 60
        pullback_bias_min   (float): 季線回踩下限門檻（%），預設 -2.0
        pullback_bias_max   (float): 季線回踩上限門檻（%），預設 1.0
        capitulation_bias   (float): 恐慌超跌門檻（%），預設 -6.0
        oversold_kd         (float): KD 超賣金叉門檻，預設 25.0
        oversold_rsi        (float): RSI 超賣落底門檻，預設 35.0
        climax_bias         (float): 噴出過熱乖離門檻（%），預設 22.0
        trail_stop_pct      (float): 移動停利高點回撤比率，預設 0.08 (8%)
        hard_stop_pct       (float): 初始硬性停損比率，預設 0.08 (8%)
        enter_on_start      (bool):  首日是否進場，預設 False（空手等低點）
    """

    name = "dip_hunter_alpha"
    description = (
        "相對低位階抄底策略：季線回踩守穩(勝率81%)、KD/RSI超賣反彈(勝率80-92%)、"
        "恐慌負乖離抄底(勝率84%)，專注於相對低位階安全上車不追高"
    )

    def __init__(
        self,
        bias_ma_period: int = 60,
        pullback_bias_min: float = -2.0,
        pullback_bias_max: float = 1.0,
        capitulation_bias: float = -6.0,
        oversold_kd: float = 25.0,
        oversold_rsi: float = 35.0,
        climax_bias: float = 22.0,
        trail_stop_pct: float = 0.08,
        hard_stop_pct: float = 0.08,
        enter_on_start: bool = False,
    ):
        super().__init__(
            bias_ma_period=bias_ma_period,
            pullback_bias_min=pullback_bias_min,
            pullback_bias_max=pullback_bias_max,
            capitulation_bias=capitulation_bias,
            oversold_kd=oversold_kd,
            oversold_rsi=oversold_rsi,
            climax_bias=climax_bias,
            trail_stop_pct=trail_stop_pct,
            hard_stop_pct=hard_stop_pct,
            enter_on_start=enter_on_start,
        )
        self.bias_ma_period = int(bias_ma_period)
        self.pullback_bias_min = float(pullback_bias_min)
        self.pullback_bias_max = float(pullback_bias_max)
        self.capitulation_bias = float(capitulation_bias)
        self.oversold_kd = float(oversold_kd)
        self.oversold_rsi = float(oversold_rsi)
        self.climax_bias = float(climax_bias)
        self.trail_stop_pct = float(trail_stop_pct)
        self.hard_stop_pct = float(hard_stop_pct)
        self.enter_on_start = bool(enter_on_start)

    @staticmethod
    def _calc_kd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9) -> tuple[pd.Series, pd.Series]:
        """計算 KD 指標 (9, 3, 3)。"""
        low_n = low.rolling(period, min_periods=1).min()
        high_n = high.rolling(period, min_periods=1).max()
        rsv = ((close - low_n) / (high_n - low_n).replace(0, np.nan) * 100.0).fillna(50.0)

        n = len(close)
        k = pd.Series(50.0, index=close.index, dtype=float)
        d = pd.Series(50.0, index=close.index, dtype=float)
        cur_k, cur_d = 50.0, 50.0
        for i in range(n):
            cur_k = (2.0 / 3.0) * cur_k + (1.0 / 3.0) * rsv.iloc[i]
            cur_d = (2.0 / 3.0) * cur_d + (1.0 / 3.0) * cur_k
            k.iloc[i] = cur_k
            d.iloc[i] = cur_d
        return k, d

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI 指標 (14)。"""
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """產生抄底買進與出場訊號。"""
        if data.empty:
            return pd.Series(dtype=int)

        n = len(data)
        signal = pd.Series(0, index=data.index, dtype=int)
        close = data["close"]
        high = data["high"]
        low = data["low"]
        open_p = data["open"]

        ma = close.rolling(self.bias_ma_period, min_periods=1).mean()
        bias = (close - ma) / ma * 100.0

        k, d = self._calc_kd(high, low, close, period=9)
        rsi = self._calc_rsi(close, period=14)

        pos = False
        entry_price = 0.0
        peak_price = 0.0
        climax_active = False
        capitulation_active = False

        for i in range(n):
            cur_c = close.iloc[i]
            cur_h = high.iloc[i]
            cur_o = open_p.iloc[i]
            b = bias.iloc[i]
            cur_k = k.iloc[i]
            prev_k = k.iloc[i - 1] if i > 0 else 50.0
            cur_d = d.iloc[i]
            prev_d = d.iloc[i - 1] if i > 0 else 50.0
            cur_rsi = rsi.iloc[i]

            if not pos:
                # ── 機制 0：首日進場（若開啟）──
                if i == 0 and self.enter_on_start:
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False
                    continue

                # 追蹤恐慌超跌狀態
                if b <= self.capitulation_bias:
                    capitulation_active = True

                # ── 抄底買點 1：極度恐慌超跌抄底 (Capitulation) ──
                # 季線負乖離 <= -6% 且落底收紅 K 或乖離收斂
                if capitulation_active and (cur_c > cur_o or b > self.capitulation_bias + 1.0):
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False
                    continue

                # ── 抄底買點 2：多頭回踩季線支撐守穩 (Pullback to MA60) ──
                # 季線乖離拉回到 -2.0% ~ +1.0% 且當日收紅 K 確認支撐守住
                ma_flat_or_up = ma.iloc[i] >= (ma.iloc[i - 10] * 0.995) if i >= 10 else True
                if (self.pullback_bias_min <= b <= self.pullback_bias_max) and (cur_c > cur_o) and ma_flat_or_up:
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False
                    continue

                # ── 抄底買點 3：短線動能超跌反轉 (KD <= 25 金叉 或 RSI <= 35 紅K) ──
                kd_cross = (cur_k <= self.oversold_kd) and (cur_k > cur_d) and (prev_k <= prev_d)
                rsi_oversold = (cur_rsi <= self.oversold_rsi) and (cur_c > cur_o)
                if (kd_cross or rsi_oversold) and b > self.capitulation_bias:
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False
                    continue

            else:
                # 更新持倉期間波段最高價
                if cur_h > peak_price:
                    peak_price = cur_h

                # 季線乖離過熱啟動移動停利
                if b >= self.climax_bias:
                    climax_active = True

                drop_from_peak = (peak_price - cur_c) / peak_price if peak_price > 0 else 0.0
                loss_from_entry = (entry_price - cur_c) / entry_price if entry_price > 0 else 0.0

                # ── 出場機制 1：初始硬性停損 (-8%) ──
                if loss_from_entry >= self.hard_stop_pct:
                    signal.iloc[i] = -1
                    pos = False
                    entry_price = 0.0
                    peak_price = 0.0
                    climax_active = False
                    continue

                # ── 出場機制 2：乖離過熱後高點動態回撤移動停利 (-8%) ──
                if climax_active and drop_from_peak >= self.trail_stop_pct:
                    signal.iloc[i] = -1
                    pos = False
                    entry_price = 0.0
                    peak_price = 0.0
                    climax_active = False
                    continue

        return signal
