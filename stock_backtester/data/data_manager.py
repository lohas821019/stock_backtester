"""
資料管理器 DataManager

統一管理所有資料來源的入口，提供：
- 自動選擇適合的 fetcher（依市場/股票代號）
- 本地快取（SQLite + Parquet）
- 自動補齊缺失資料
"""

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from .fetchers.twse_fetcher import TWSEFetcher
from .fetchers.tpex_fetcher import TPEXFetcher
from .fetchers.yfinance_fetcher import YFinanceFetcher
from .storage.database import Database

logger = logging.getLogger(__name__)

# 預設快取目錄
_DEFAULT_CACHE_DIR = Path.home() / ".stock_backtester" / "cache"


class DataManager:
    """
    統一資料入口。

    自動選擇資料來源：
    - 台股日線：優先 TWSE/TPEX，fallback yfinance
    - 分鐘線：使用 yfinance
    - 美股：使用 yfinance

    所有資料都會快取到本地 SQLite 資料庫，避免重複下載。

    使用範例：
        dm = DataManager()
        df = dm.get_ohlcv("2330", date(2024, 1, 1), date(2024, 12, 31))
        df_min = dm.get_ohlcv("2330.TW", date.today(), date.today(), interval="5min")
    """

    def __init__(self, cache_dir: Path | str | None = None):
        self._cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._db = Database(self._cache_dir / "ohlcv.db")
        self._twse = TWSEFetcher()
        self._tpex = TPEXFetcher()
        self._yf = YFinanceFetcher()

        logger.info("[DataManager] 快取目錄: %s", self._cache_dir)

    def get_ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
        market: str = "auto",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        取得 OHLCV 資料（含本地快取與自動除權息還原）。
        """
        from datetime import timedelta
        cache_key = f"{symbol}_{interval}"
        self.last_cache_hit = False
        today = date.today()

        if interval == "1d":
            if not force_refresh:
                # 先查本地 SQLite 快取
                cached = self._db.load(cache_key, start, end)
                if cached is not None and not cached.empty:
                    missing_ranges = self._find_missing_ranges(cached, start, end)
                    if not missing_ranges:
                        # 若 end 是今天，額外補抓最近 7 天確保收盤價最新
                        if end >= today:
                            tail_start = max(start, today - timedelta(days=7))
                            logger.info("[DataManager] 📡 補抓最近 7 天尾端資料確保今日收盤: %s", symbol)
                            tail_df = self._fetch_tw_daily(symbol, tail_start, end, market)
                            if not tail_df.empty:
                                self._db.save(cache_key, tail_df)
                        else:
                            logger.info("[DataManager] ⚡ 快取命中: %s (%s ~ %s) 共 %d 筆，無需重複下載",
                                        symbol, start, end, len(cached))
                            self.last_cache_hit = True
                            return self._adjust_0052(symbol, cached, cache_key)
                else:
                    missing_ranges = [(start, end)]
            else:
                logger.info("[DataManager] 🔄 強制重新下載最新資料: %s", symbol)
                missing_ranges = [(start, end)]

            # 補充缺失資料（增量下載）
            new_frames = []
            for miss_start, miss_end in missing_ranges:
                logger.info("[DataManager] 🌐 下載還原權息資料 %s (%s ~ %s)...",
                            symbol, miss_start, miss_end)
                fetched = self._fetch_tw_daily(symbol, miss_start, miss_end, market)
                if not fetched.empty:
                    new_frames.append(fetched)

            if new_frames:
                new_data = pd.concat(new_frames)
                self._db.save(cache_key, new_data)
                logger.info("[DataManager] ✅ 已成功存入 SQLite 快取，下次同區間回測無需下載")

            # 重新讀取完整快取
            result = self._db.load(cache_key, start, end)
            if result is not None and not result.empty:
                result = result.dropna(subset=["open", "high", "low", "close"])
                result = result[(result["close"] > 0) & (result["open"] > 0)]
                return self._adjust_0052(symbol, result, cache_key)
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            )

        else:
            # 分鐘線：直接使用 yfinance（自動加 .TW 後綴給台股）
            yf_symbol = self._to_yf_symbol(symbol, market)
            df_min = self._yf.fetch(yf_symbol, start, end, interval)
            if not df_min.empty:
                df_min = df_min.dropna(subset=["open", "high", "low", "close"])
                df_min = df_min[(df_min["close"] > 0) & (df_min["open"] > 0)]
            return df_min

    def _adjust_0052(self, symbol: str, df: pd.DataFrame, cache_key: str | None = None) -> pd.DataFrame:
        """0052 富邦科技於 2025/11/17 進行 1 拆 7 股票分割之自動還原防護。"""
        if symbol == "0052" and df is not None and not df.empty:
            split_cutoff = pd.Timestamp("2025-11-17")
            if getattr(df.index, "tz", None) is not None:
                split_cutoff = split_cutoff.tz_localize(df.index.tz)
            mask = df.index < split_cutoff
            if mask.any() and df.loc[mask, "close"].max() > 100:
                logger.info("[DataManager] 🛡️ 執行 0052 歷史資料 1 拆 7 股票分割自動除權息還原")
                df = df.copy()
                df.loc[mask, ["open", "high", "low", "close"]] /= 7.0
                df.loc[mask, "volume"] *= 7.0
                if cache_key:
                    self._db.save(cache_key, df)
        return df

    def _fetch_tw_daily(
        self, symbol: str, start: date, end: date, market: str
    ) -> pd.DataFrame:
        """
        抓取台股日線。
        重要：為避免除權、除息與股票分割（如 0050 於 2025/6 進行 1 拆 4 分割）
        造成股價斷層假象，優先使用具備 auto_adjust=True 的還原權息資料源。
        """
        # 純數字代號 → 台股
        if symbol.isdigit():
            # 優先使用 yfinance 還原價，消除股票分割/除息造成的斷層
            yf_symbol = f"{symbol}.TWO" if market == "tw_otc" else f"{symbol}.TW"
            try:
                logger.info("[DataManager] 優先使用 yfinance 抓取還原權息股價: %s", yf_symbol)
                df = self._yf.fetch(yf_symbol, start, end)
                if not df.empty:
                    return self._adjust_0052(symbol, df)
            except Exception as e:
                logger.warning("[DataManager] yfinance 抓取失敗，嘗試官方 TWSE/TPEX: %s", e)

            # Fallback 到官方 TWSE / TPEX
            if market in ("auto", "tw_listed"):
                try:
                    df = self._twse.fetch(symbol, start, end)
                    if not df.empty:
                        return self._adjust_0052(symbol, df)
                except Exception as e:
                    logger.warning("[DataManager] TWSE 失敗: %s", e)

            if market in ("auto", "tw_otc"):
                try:
                    df = self._tpex.fetch(symbol, start, end)
                    if not df.empty:
                        return self._adjust_0052(symbol, df)
                except Exception as e:
                    logger.warning("[DataManager] TPEX 失敗: %s", e)

            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        else:
            # 美股或已有後綴
            return self._yf.fetch(symbol, start, end)

    @staticmethod
    def _to_yf_symbol(symbol: str, market: str) -> str:
        """將台股代號轉換為 yfinance 格式。"""
        if "." in symbol:
            return symbol  # 已有後綴
        if symbol.isdigit():
            if market == "tw_otc":
                return f"{symbol}.TWO"
            return f"{symbol}.TW"
        return symbol  # 美股

    @staticmethod
    def _find_missing_ranges(
        cached: pd.DataFrame, start: date, end: date
    ) -> list[tuple[date, date]]:
        """找出快取中缺失的日期範圍（簡化版：只看首尾）。"""
        missing = []

        cached_dates = cached.index.date
        if len(cached_dates) == 0:
            return [(start, end)]

        cached_start = cached_dates.min()
        cached_end = cached_dates.max()

        # 前端容忍 <= 4 天（假日邊界），後端只要差 >= 1 天就補抓新資料
        # 注意：Streamlit 的 @cache_data(ttl=600) 已防止 10 分鐘內重複呼叫
        if start < cached_start and (cached_start - start).days > 4:
            missing.append((start, cached_start))
        if end > cached_end and (end - cached_end).days >= 1:
            missing.append((cached_end, end))

        return missing
