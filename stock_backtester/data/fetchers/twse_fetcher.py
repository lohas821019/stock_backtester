"""
TWSE（台灣證券交易所）資料抓取器

資料來源：https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY
- 支援台灣上市股票日線 OHLCV
- 免費，不需帳號
- 限制：每次抓取一個月的資料，需逐月循環

注意：TWSE API 僅提供日線資料，不支援分鐘線。
"""

import time
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

import requests
import pandas as pd

from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

_TWSE_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"


class TWSEFetcher(BaseFetcher):
    """
    台灣上市股票日線抓取器（TWSE）。

    範例：
        fetcher = TWSEFetcher()
        df = fetcher.fetch("2330", date(2024, 1, 1), date(2024, 12, 31))
    """

    source_name = "TWSE"

    def __init__(self, request_delay: float = 0.5):
        """
        Args:
            request_delay: 每次 API 請求之間的等待秒數，避免被限流。
        """
        self._delay = request_delay
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.twse.com.tw/",
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
        抓取台灣上市股票日線資料。

        Args:
            symbol:   股票代號，例如 "2330"（台積電）
            start:    開始日期
            end:      結束日期
            interval: 僅支援 "1d"（日線）

        Returns:
            標準 OHLCV DataFrame
        """
        if interval != "1d":
            raise ValueError(f"[TWSE] 僅支援日線 (interval='1d')，不支援: {interval}")

        all_frames: list[pd.DataFrame] = []
        current = date(start.year, start.month, 1)

        while current <= end:
            logger.info("[TWSE] 抓取 %s %s-%02d ...", symbol, current.year, current.month)
            df = self._fetch_month(symbol, current)

            if df is not None and not df.empty:
                # 篩選日期範圍
                df = df[(df.index.date >= start) & (df.index.date <= end)]
                if not df.empty:
                    all_frames.append(df)

            current += relativedelta(months=1)
            time.sleep(self._delay)

        if not all_frames:
            logger.warning("[TWSE] %s 在指定日期範圍內無資料", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result = pd.concat(all_frames).sort_index()
        # 移除可能的重複索引
        result = result[~result.index.duplicated(keep="first")]
        return result

    def _fetch_month(self, symbol: str, month_start: date) -> pd.DataFrame | None:
        """抓取單個月份的資料。"""
        date_str = month_start.strftime("%Y%m%d")
        params = {
            "date": date_str,
            "stockNo": symbol,
            "response": "json",
        }

        try:
            resp = self._session.get(_TWSE_DAY_URL, params=params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            logger.error("[TWSE] 請求失敗 %s %s: %s", symbol, date_str, e)
            return None
        except ValueError as e:
            logger.error("[TWSE] JSON 解析失敗 %s %s: %s", symbol, date_str, e)
            return None

        if payload.get("stat") != "OK":
            logger.debug("[TWSE] stat != OK: %s", payload.get("stat"))
            return None

        fields = payload.get("fields", [])
        data = payload.get("data", [])

        if not data:
            return None

        df = pd.DataFrame(data, columns=fields)
        return self._parse_twse_df(df)

    def _parse_twse_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """將 TWSE API 回傳格式轉換為標準 OHLCV DataFrame。"""
        # TWSE 日期格式為「民國年/月/日」，例如 "113/01/02"
        def _parse_roc_date(roc_str: str) -> pd.Timestamp:
            parts = roc_str.strip().split("/")
            year = int(parts[0]) + 1911
            return pd.Timestamp(f"{year}-{parts[1]}-{parts[2]}")

        df["date"] = df["日期"].apply(_parse_roc_date)
        df = df.set_index("date")
        df.index = pd.DatetimeIndex(df.index)

        # 欄位名稱映射
        col_map = {
            "開盤價": "open",
            "最高價": "high",
            "最低價": "low",
            "收盤價": "close",
            "成交股數": "volume",
        }

        # 選擇並重命名欄位
        available = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=available)

        # 清理數字格式（移除逗號、空白、X/+ 等符號）
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",", "", regex=False)
                    .str.strip()
                    .str.replace(r"[^0-9.]", "", regex=True)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return self._normalize(df)
