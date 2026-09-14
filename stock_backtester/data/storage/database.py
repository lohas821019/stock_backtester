"""
本地 SQLite 資料庫管理

儲存 OHLCV 快取資料，避免重複下載。
"""

import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite OHLCV 快取資料庫。

    每個 symbol + interval 組合對應一張 table，
    table 名稱格式為：ohlcv_{symbol}_{interval}（符號中的 . 替換為 _）

    使用範例：
        db = Database("cache/ohlcv.db")
        db.save("2330_1d", df)
        df = db.load("2330_1d", date(2024, 1, 1), date(2024, 12, 31))
    """

    def __init__(self, db_path: Path | str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{self._path}")
        logger.info("[Database] 使用資料庫: %s", self._path)

    def _table_name(self, cache_key: str) -> str:
        """將 cache_key 轉換為合法的 table 名稱。"""
        return "ohlcv_" + cache_key.replace(".", "_").replace("-", "_").lower()

    def save(self, cache_key: str, df: pd.DataFrame) -> None:
        """
        儲存 OHLCV 資料到資料庫（UPSERT）。

        Args:
            cache_key: 唯一鍵，如 "2330_1d"
            df:        標準 OHLCV DataFrame
        """
        if df.empty:
            return

        table = self._table_name(cache_key)
        df_to_save = df.copy()
        df_to_save.index.name = "date"
        df_to_save = df_to_save.reset_index()
        df_to_save["date"] = df_to_save["date"].astype(str)

        with self._engine.begin() as conn:
            # 使用 pandas to_sql replace 模式（若資料量小可接受）
            # 生產環境應改用 UPSERT
            existing = self._load_raw(cache_key)
            if existing is not None and not existing.empty:
                combined = pd.concat([existing, df]).drop_duplicates(
                    subset=None, keep="last"
                )
                combined = combined[~combined.index.duplicated(keep="last")]
            else:
                combined = df

            # 嚴格過濾無效價格列，防止儲存任何 NaN 或非正數價格
            combined = combined.dropna(subset=["open", "high", "low", "close"])
            combined = combined[(combined["open"] > 0) & (combined["close"] > 0)]

            combined_to_save = combined.copy()
            combined_to_save.index.name = "date"
            combined_to_save = combined_to_save.reset_index()
            combined_to_save["date"] = combined_to_save["date"].astype(str)
            combined_to_save.to_sql(table, conn, if_exists="replace", index=False)

        logger.debug("[Database] 已儲存 %d 筆資料到 %s", len(df), table)

    def load(
        self, cache_key: str, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame | None:
        """
        從資料庫讀取 OHLCV 資料。

        Args:
            cache_key: 唯一鍵
            start:     開始日期（含）
            end:       結束日期（含）

        Returns:
            DataFrame 或 None（若無資料）
        """
        df = self._load_raw(cache_key)
        if df is None or df.empty:
            return None

        if start is not None:
            df = df[df.index.date >= start]
        if end is not None:
            df = df[df.index.date <= end]

        return df if not df.empty else None

    def _load_raw(self, cache_key: str) -> pd.DataFrame | None:
        """讀取整個 table。"""
        table = self._table_name(cache_key)
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                    {"t": table},
                )
                if result.fetchone() is None:
                    return None

                df = pd.read_sql(f"SELECT * FROM {table}", conn)
                if df.empty:
                    return None

                # 統一使用 format="mixed" 並移除時區偏差，確保相容所有資料來源
                parsed_dates = pd.to_datetime(df["date"], format="mixed", utc=True).dt.tz_localize(None)
                df["date"] = parsed_dates
                df = df.set_index("date")
                df.index = pd.DatetimeIndex(df.index)
                return df.sort_index()

        except Exception as e:
            logger.warning("[Database] 讀取失敗 %s: %s", table, e)
            return None

    def list_cached(self) -> list[str]:
        """列出所有已快取的 cache_key。"""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ohlcv_%'")
                )
                return [
                    row[0].replace("ohlcv_", "", 1) for row in result.fetchall()
                ]
        except Exception:
            return []
