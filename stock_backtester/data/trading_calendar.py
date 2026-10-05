"""
台股交易日曆 (TWSE Trading Calendar)

資料來源：證交所「市場開休市日期」
    https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&date=YYYY0101

注意：該清單同時包含「休市日」與「開始交易日 / 最後交易日」等說明性項目，
名稱含「開始交易」或「最後交易」者為正常交易日，其餘皆視為休市。

快取：每年一份 JSON 存於 ~/.stock_backtester/cache/twse_holidays_{year}.json，
GitHub Actions 會透過 actions/cache 一併持久化，一年只需下載一次。

失敗策略：無法取得休市日資料時「視為交易日」(fail-open)，
寧可在假日多發一則訊息，也不要在交易日漏掉盤中監控。
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HOLIDAY_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule"
_TRADING_KEYWORDS = ("開始交易", "最後交易")
DEFAULT_CACHE_DIR = Path.home() / ".stock_backtester" / "cache"


def _parse_closed_dates(payload: dict) -> set[str]:
    """從 TWSE 回傳 JSON 解析出休市日期集合（YYYY-MM-DD）。"""
    closed: set[str] = set()
    for row in payload.get("data", []):
        if len(row) < 2:
            continue
        d_str, name = str(row[0]).strip(), str(row[1])
        if any(k in name for k in _TRADING_KEYWORDS):
            continue
        closed.add(d_str)
    return closed


def get_closed_dates(year: int, cache_dir: Optional[Path] = None) -> Optional[set[str]]:
    """取得指定年度的休市日集合；無法取得時回傳 None。"""
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    cache_file = cache_dir / f"twse_holidays_{year}.json"

    if cache_file.exists():
        try:
            return set(json.loads(cache_file.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"[TradingCalendar] 讀取休市日快取失敗，改為重新下載: {e}")

    try:
        resp = requests.get(
            HOLIDAY_URL,
            params={"response": "json", "date": f"{year}0101"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("stat") != "ok" or not payload.get("data"):
            logger.warning(f"[TradingCalendar] TWSE 休市日資料異常: stat={payload.get('stat')}")
            return None
        closed = _parse_closed_dates(payload)
    except Exception as e:
        logger.warning(f"[TradingCalendar] 下載 {year} 年休市日失敗: {e}")
        return None

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(sorted(closed), ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[TradingCalendar] 寫入休市日快取失敗: {e}")

    return closed


def is_trading_day(d: date, cache_dir: Optional[Path] = None) -> bool:
    """判斷指定日期是否為台股交易日。週末一律休市；資料取得失敗時視為交易日。"""
    if d.weekday() >= 5:
        return False

    closed = get_closed_dates(d.year, cache_dir=cache_dir)
    if closed is None:
        logger.warning(f"[TradingCalendar] 無法取得休市日資料，{d} 預設視為交易日")
        return True
    return d.strftime("%Y-%m-%d") not in closed
