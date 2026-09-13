"""
TPEX（台灣櫃買中心）資料抓取器

資料來源：https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php
- 支援台灣上櫃股票日線 OHLCV
- 免費，不需帳號
- 限制：每次抓取一個月的資料，需逐月循環

注意：TPEX API 僅提供日線資料，不支援分鐘線。
"""

import time
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

import requests
import pandas as pd

from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

_TPEX_DAY_URL = (
    "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php"
)


class TPEXFetcher(BaseFetcher):
    """
    台灣上櫃股票日線抓取器（TPEX 櫃買中心）。

    範例：
        fetcher = TPEXFetcher()
        df = fetcher.fetch("6547", date(2024, 1, 1), date(2024, 12, 31))
    """

    source_name = "TPEX"

    def __init__(self, request_delay: float = 0.5):
        self._delay = request_delay
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.tpex.org.tw/",
            }
        )

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        抓取台灣上櫃股票日線資料。

        Args:
            symbol:   股票代號，例如 "6547"
            start:    開始日期
            end:      結束日期
            interval: 僅支援 "1d"（日線）

        Returns:
            標準 OHLCV DataFrame
        """
        if interval != "1d":
            raise ValueError(f"[TPEX] 僅支援日線 (interval='1d')，不支援: {interval}")

        all_frames: list[pd.DataFrame] = []
        current = date(start.year, start.month, 1)

        while current <= end:
            logger.info("[TPEX] 抓取 %s %s-%02d ...", symbol, current.year, current.month)
            df = self._fetch_month(symbol, current)

            if df is not None and not df.empty:
                df = df[(df.index.date >= start) & (df.index.date <= end)]
                if not df.empty:
                    all_frames.append(df)

            current += relativedelta(months=1)
            time.sleep(self._delay)

        if not all_frames:
            logger.warning("[TPEX] %s 在指定日期範圍內無資料", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result = pd.concat(all_frames).sort_index()
        result = result[~result.index.duplicated(keep="first")]
        return result

    def _fetch_month(self, symbol: str, month_start: date) -> pd.DataFrame | None:
        """抓取單個月份的資料。"""
        # TPEX 使用民國年月格式：YYYY/MM（民國年）
        roc_year = month_start.year - 1911
        date_str = f"{roc_year}/{month_start.month:02d}"

        params = {
            "d": date_str,
            "stkno": symbol,
            "o": "json",
        }

        try:
            resp = self._session.get(_TPEX_DAY_URL, params=params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            logger.error("[TPEX] 請求失敗 %s %s: %s", symbol, date_str, e)
            return None
        except ValueError as e:
            logger.error("[TPEX] JSON 解析失敗 %s %s: %s", symbol, date_str, e)
            return None

        aa_data = payload.get("aaData", [])
        if not aa_data:
            return None

        return self._parse_tpex_data(aa_data, month_start.year)

    def _parse_tpex_data(self, aa_data: list, year: int) -> pd.DataFrame:
        """將 TPEX aaData 格式轉換為標準 OHLCV DataFrame。"""
        records = []
        for row in aa_data:
            # row[0] = "民國年/月/日"，row[3]=開, row[4]=高, row[5]=低, row[6]=收, row[1]=成交張數
            try:
                parts = str(row[0]).strip().split("/")
                roc_year = int(parts[0])
                western_year = roc_year + 1911
                dt = pd.Timestamp(f"{western_year}-{parts[1]}-{parts[2]}")

                def clean(val: str) -> float:
                    return float(str(val).replace(",", "").strip() or "nan")

                records.append(
                    {
                        "date": dt,
                        "open": clean(row[3]),
                        "high": clean(row[4]),
                        "low": clean(row[5]),
                        "close": clean(row[6]),
                        # TPEX 成交量單位為「張」，換算為股（*1000）
                        "volume": clean(row[1]) * 1000,
                    }
                )
            except (IndexError, ValueError, TypeError) as e:
                logger.debug("[TPEX] 略過無法解析的列: %s (%s)", row, e)
                continue

        if not records:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.DataFrame(records).set_index("date")
        df.index = pd.DatetimeIndex(df.index)
        return self._normalize(df)
