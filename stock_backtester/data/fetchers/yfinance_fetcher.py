"""
yfinance 資料抓取器

資料來源：Yahoo Finance（透過 yfinance 套件）
- 支援台股（需加後綴 .TW / .TWO）與美股
- 日線：無年份限制
- 分鐘線：限近 60 天
- 免費，不需帳號

支援的 interval：
    "1d"   - 日線
    "1min" - 1 分鐘線（別名 "1m"）
    "5min" - 5 分鐘線
    "15min"- 15 分鐘線
    "60min"- 60 分鐘線（別名 "1h"）
"""

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# yfinance interval 映射表
_INTERVAL_MAP = {
    "1d": "1d",
    "1min": "1m",
    "5min": "5m",
    "15min": "15m",
    "60min": "1h",
}

# 分鐘線最多往前抓 60 天
_INTRADAY_MAX_DAYS = 60


class YFinanceFetcher(BaseFetcher):
    """
    Yahoo Finance 資料抓取器，支援台股與美股。

    台股代號需加後綴：
        上市（TWSE）：2330 → "2330.TW"
        上櫃（TPEX）：6547 → "6547.TWO"

    使用 auto_suffix=True 時，會自動嘗試補上 .TW 後綴。

    範例：
        fetcher = YFinanceFetcher()
        # 台股日線
        df = fetcher.fetch("2330.TW", date(2024, 1, 1), date(2024, 12, 31))
        # 美股分鐘線
        df = fetcher.fetch("TSMC", date.today() - timedelta(days=5), date.today(), interval="5min")
    """

    source_name = "yfinance"

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Args:
            symbol:   股票代號。台股請加後綴（如 "2330.TW"）
            start:    開始日期
            end:      結束日期
            interval: "1d" / "1min" / "5min" / "15min" / "60min"

        Returns:
            標準 OHLCV DataFrame
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError(
                "請先安裝 yfinance：pip install yfinance"
            )

        yf_interval = _INTERVAL_MAP.get(interval)
        if yf_interval is None:
            raise ValueError(
                f"[yfinance] 不支援的 interval: {interval}。"
                f"可用選項: {list(_INTERVAL_MAP.keys())}"
            )

        # 分鐘線限制 60 天
        if interval != "1d":
            min_start = date.today() - timedelta(days=_INTRADAY_MAX_DAYS)
            if start < min_start:
                logger.warning(
                    "[yfinance] 分鐘線僅支援近 %d 天，調整 start 為 %s",
                    _INTRADAY_MAX_DAYS,
                    min_start,
                )
                start = min_start

        # yfinance end 日期為 exclusive，需加一天
        end_exclusive = end + timedelta(days=1)

        logger.info(
            "[yfinance] 抓取 %s %s ~ %s (interval=%s) ...",
            symbol, start, end, yf_interval,
        )

        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            interval=yf_interval,
            auto_adjust=True,
            prepost=False,
        )

        if raw.empty:
            logger.warning("[yfinance] %s 在指定日期範圍內無資料", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        return self._normalize(raw)
