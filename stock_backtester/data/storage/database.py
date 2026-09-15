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
        """將 cache_key 轉換為合法的 table 名稱（含 v4 版本號，自動淘汰雲端舊快取）。"""
        return "ohlcv_v4_" + cache_key.replace(".", "_").replace("-", "_").lower()

    @staticmethod
    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        """統一將 DataFrame index 正規化為乾淨的無時區 DatetimeIndex (以台北時間為基準日)。"""
        if df.empty:
            return df
        df = df.copy()
        if hasattr(df.index, "tz") and df.index.tz is not None:
            norm_idx = df.index.tz_convert("Asia/Taipei").tz_localize(None).normalize()
        else:
            norm_idx = pd.to_datetime(df.index).normalize()
        df.index = norm_idx
        df.index.name = "date"
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df[(df["open"] > 0) & (df["close"] > 0)]
        return df

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
        df_norm = self._normalize_df(df)

        with self._engine.begin() as conn:
            existing = self._load_raw(cache_key)
            if existing is not None and not existing.empty:
                existing_norm = self._normalize_df(existing)
                combined = pd.concat([existing_norm, df_norm])
                # 以日期為唯一索引去重，保留最新資料並按時間升冪排序
                combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            else:
                combined = df_norm

            combined_to_save = combined.copy().reset_index()
            combined_to_save["date"] = combined_to_save["date"].dt.strftime("%Y-%m-%d")
            combined_to_save.to_sql(table, conn, if_exists="replace", index=False)

        logger.debug("[Database] 已儲存 %d 筆資料到 %s", len(combined), table)

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

                # 直接解析 YYYY-MM-DD，正規化為乾淨的 DatetimeIndex
                df["date"] = pd.to_datetime(df["date"].str[:10])
                df = df.set_index("date")
                df.index = pd.DatetimeIndex(df.index).normalize()
                return df.sort_index()

        except Exception as e:
            logger.warning("[Database] 讀取失敗 %s: %s", table, e)
            return None

    def list_cached(self) -> list[str]:
        """列出所有已快取的 cache_key。"""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ohlcv_v4_%'")
                )
                return [
                    row[0].replace("ohlcv_v4_", "", 1) for row in result.fetchall()
                ]
        except Exception:
            return []
