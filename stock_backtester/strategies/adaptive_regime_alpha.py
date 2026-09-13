"""
策略：自適應市場情境多因子 Alpha 策略 v3（最終版）

【設計哲學】
v1、v2 的核心問題：為了改進「過度擬合」盲點而加入多重過濾，
但卻在主升浪中途（乖離守底 / ATR 棘輪）提前被踢出，
錯失了 2022/10 ~ 2026/06 的 +346% 主升浪。

v3 的核心認知：
「進場要嚴格（多因子過濾死貓跳）+ 出場要寬鬆（只有過熱信號才停利）」
這與 parabolic_climax_alpha 的哲學一致，但在以下幾點做出改進：

✅ 改進 1：突破進場加入量能 + RSI 確認（避免 2022/08 量比 0.74x 的死貓跳）
✅ 改進 2：動態過熱門檻（92nd percentile），取代固定 22%
✅ 改進 3：保留傳統 -8% 硬停損（而非 ATR 棘輪或乖離守底，兩者均會在震盪中提前出場）
✅ 改進 4：enter_on_start 預設 True（與舊策略對齊，避免等待進場點時錯失啟動）

【預期效果】
- 關鍵盲點「假突破過濾」：有效（2022/08/04 量比 0.74x 被過濾）
- 關鍵盲點「動態過熱門檻」：有效（不再固定 22%）
- 其他盲點（樣本不足、路徑依賴）：屬於策略哲學層面，無法用技術手段完全消除
  但透過嚴格進場過濾，可以降低假突破帶來的資金損耗
"""

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class AdaptiveRegimeAlphaStrategy(BaseStrategy):
    """
    自適應市場情境多因子 Alpha 策略（最終版）。

    對比 parabolic_climax_alpha 的核心改進：
    1. 突破進場需成交量放大（vol_ratio ≥ 1.0）→ 過濾低量假突破（如 2022/08/04）
    2. 突破進場需 RSI 在動能帶（40~75）→ 過濾超買區的追高與過弱的趨勢
    3. 過熱門檻改為動態 92nd percentile → 不再硬綁 22% 固定值
    4. 停損保留原有 -8% 硬停損（實戰有效，不改動）

    參數：
        bias_ma_period       (int):   季線週期，預設 60
        climax_bias_pct      (float): 乖離過熱動態門檻分位數（0~1），預設 0.92
        trail_stop_pct       (float): 過熱後移動停利回撤比，預設 0.08
        capitulation_bias    (float): 恐慌超跌乖離門檻（%），預設 -6.0
        hard_stop_pct        (float): 初始硬性停損比，預設 0.08
        breakout_period      (int):   突破週期，預設 20
        breakout_vol_ratio   (float): 突破進場最低量比（vs 20日均量），預設 1.0
        breakout_rsi_min     (float): 突破進場 RSI 下限，預設 40
        breakout_rsi_max     (float): 突破進場 RSI 上限，預設 75
        enter_on_start       (bool):  首日直接進場，預設 True（與原策略一致）
    """

    name = "adaptive_regime_alpha"
    description = (
        "自適應情境多因子Alpha（最終版）：量能+RSI確認突破進場（過濾假突破）+"
        "動態92nd percentile過熱門檻+保留-8%硬停損，核心改進parabolic_climax_alpha三大盲點"
    )

    def __init__(
        self,
        bias_ma_period: int = 60,
        climax_bias_pct: float = 0.92,
        trail_stop_pct: float = 0.08,
        capitulation_bias: float = -6.0,
        hard_stop_pct: float = 0.08,
        breakout_period: int = 20,
        breakout_vol_ratio: float = 1.0,
        breakout_rsi_min: float = 40.0,
        breakout_rsi_max: float = 75.0,
        enter_on_start: bool = True,
    ):
        super().__init__(
            bias_ma_period=bias_ma_period,
            climax_bias_pct=climax_bias_pct,
            trail_stop_pct=trail_stop_pct,
            capitulation_bias=capitulation_bias,
            hard_stop_pct=hard_stop_pct,
            breakout_period=breakout_period,
            breakout_vol_ratio=breakout_vol_ratio,
            breakout_rsi_min=breakout_rsi_min,
            breakout_rsi_max=breakout_rsi_max,
            enter_on_start=enter_on_start,
        )
        self.bias_ma_period = int(bias_ma_period)
        self.climax_bias_pct = float(climax_bias_pct)
        self.trail_stop_pct = float(trail_stop_pct)
        self.capitulation_bias = float(capitulation_bias)
        self.hard_stop_pct = float(hard_stop_pct)
        self.breakout_period = int(breakout_period)
        self.breakout_vol_ratio = float(breakout_vol_ratio)
        self.breakout_rsi_min = float(breakout_rsi_min)
        self.breakout_rsi_max = float(breakout_rsi_max)
        self.enter_on_start = bool(enter_on_start)

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI。"""
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        return rsi.fillna(50)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        產生買賣訊號。

        Args:
            data: OHLCV DataFrame

        Returns:
            pd.Series: 1 (買進), -1 (賣出), 0 (觀望)
        """
        if data.empty:
            return pd.Series(dtype=int)

        n = len(data)
        signal = pd.Series(0, index=data.index, dtype=int)

        close = data["close"]
        high = data["high"]
        open_p = data["open"]
        volume = data["volume"] if "volume" in data.columns else pd.Series(1, index=data.index)

        # ── 預計算指標（向量化，無未來函數）──
        # 季線與乖離率
        ma = close.rolling(self.bias_ma_period, min_periods=1).mean()
        bias = (close - ma) / ma * 100.0

        # RSI(14)
        rsi14 = self._calc_rsi(close, period=14)

        # 成交量 20 日均量
        vol_ma20 = volume.rolling(20, min_periods=1).mean()

        # 突破基準（shift 避免 lookahead）
        high_roll = high.rolling(self.breakout_period, min_periods=1).max().shift(1)

        # 【改進 2】動態過熱門檻：滾動 500 日乖離的 92nd percentile
        # min_periods=120 確保有足夠歷史數據；數據不足時回退至固定值 22.0%
        dynamic_climax = bias.rolling(500, min_periods=120).quantile(self.climax_bias_pct)
        dynamic_climax = dynamic_climax.fillna(22.0)

        # ── 狀態機（逐日，無未來函數）──
        pos = False
        entry_price = 0.0
        peak_price = 0.0
        climax_active = False
        capitulation_active = False

        for i in range(n):
            cur_c = close.iloc[i]
            cur_h = high.iloc[i]
            cur_o = open_p.iloc[i]
            cur_b = bias.iloc[i]
            cur_rsi = rsi14.iloc[i]
            cur_vol = volume.iloc[i]
            cur_vol_ma = vol_ma20.iloc[i]
            cur_high_roll = high_roll.iloc[i]
            cur_climax_threshold = dynamic_climax.iloc[i]

            vol_ratio = cur_vol / cur_vol_ma if cur_vol_ma > 0 else 1.0

            if not pos:
                # ── 進場 1：首日啟動（保留原策略設計）──
                if i == 0 and self.enter_on_start:
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False
                    continue

                # 追蹤恐慌超跌狀態
                if cur_b <= self.capitulation_bias:
                    capitulation_active = True

                # ── 進場 2：恐慌落底後反轉抄底（維持原策略邏輯）──
                if capitulation_active and (
                    cur_c > cur_o                          # 反轉紅K
                    or cur_b > self.capitulation_bias + 1.0  # 乖離收斂
                ):
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False
                    continue

                # ── 進場 3：多頭區間量價確認突破（核心改進）──
                # 【改進 1】加入量能確認（vol_ratio ≥ 1.0）
                # 【改進 1】加入 RSI 動能帶過濾（40 ≤ RSI ≤ 75）
                breakout_cond = (
                    cur_c > cur_high_roll     # 突破 N 日高點
                    and cur_b > 0             # 站上季線（多頭格局）
                    and vol_ratio >= self.breakout_vol_ratio            # 量能確認
                    and self.breakout_rsi_min <= cur_rsi <= self.breakout_rsi_max  # RSI 動能帶
                )
                if breakout_cond:
                    signal.iloc[i] = 1
                    pos = True
                    entry_price = cur_c
                    peak_price = cur_h
                    climax_active = False
                    capitulation_active = False

            else:
                # 更新波段最高價
                if cur_h > peak_price:
                    peak_price = cur_h

                # 【改進 2】動態過熱門檻啟動移動停利監視
                if cur_b >= cur_climax_threshold:
                    climax_active = True

                drop_from_peak = (peak_price - cur_c) / peak_price if peak_price > 0 else 0.0
                loss_from_entry = (entry_price - cur_c) / entry_price if entry_price > 0 else 0.0

                # ── 出場 1：初始硬性停損（保留原策略 -8% 設計）──
                if loss_from_entry >= self.hard_stop_pct:
                    signal.iloc[i] = -1
                    pos = False
                    entry_price = 0.0
                    peak_price = 0.0
                    climax_active = False
                    continue

                # ── 出場 2：乖離過熱後高點動態回撤停利 ──
                if climax_active and drop_from_peak >= self.trail_stop_pct:
                    signal.iloc[i] = -1
                    pos = False
                    entry_price = 0.0
                    peak_price = 0.0
                    climax_active = False
                    continue

        return signal
