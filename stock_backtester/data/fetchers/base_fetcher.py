"""
資料抓取器抽象基底類別

所有 fetcher 必須繼承此類別，實作 fetch() 方法。
"""

from abc import ABC, abstractmethod
from datetime import date
import pandas as pd


class BaseFetcher(ABC):
    """
    資料抓取器基底類別。

    子類別需實作：
        fetch(symbol, start, end) -> pd.DataFrame
    """

    source_name: str = "unknown"

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        抓取指定股票代號在指定日期範圍內的 OHLCV 資料。

        Args:
            symbol:   股票代號（台股如 "2330"，美股如 "TSM"）
            start:    開始日期
            end:      結束日期
            interval: 資料粒度，支援 "1d", "1min", "5min", "15min", "60min"

        Returns:
            pd.DataFrame，columns = [open, high, low, close, volume]
            index = DatetimeIndex（UTC 時區正規化）
        """
        raise NotImplementedError

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        將 DataFrame 正規化為標準格式：
        - index 為 DatetimeIndex
        - columns 為小寫：open, high, low, close, volume
        - 數值欄位為 float64
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                raise ValueError(
                    f"[{self.source_name}] 缺少必要欄位: {col}，現有欄位: {list(df.columns)}"
                )

        df = df[required]
        df[required[:4]] = df[required[:4]].astype(float)
        df["volume"] = df["volume"].astype(float)

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        return df.sort_index()
