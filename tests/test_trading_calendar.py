from datetime import date
from unittest.mock import MagicMock, patch

from stock_backtester.data import trading_calendar as tc

SAMPLE_PAYLOAD = {
    "stat": "ok",
    "data": [
        ["2026-01-01", "中華民國開國紀念日", ""],
        ["2026-01-02", "國曆新年開始交易日", ""],
        ["2026-02-11", "農曆春節前最後交易日", ""],
        ["2026-02-12", "市場無交易，僅辦理結算交割作業", ""],
        ["2026-10-09", "國慶日", ""],
    ],
}


def _mock_resp(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_parse_closed_dates_excludes_trading_markers():
    closed = tc._parse_closed_dates(SAMPLE_PAYLOAD)
    assert closed == {"2026-01-01", "2026-02-12", "2026-10-09"}


def test_is_trading_day_holiday_weekday_weekend(tmp_path):
    with patch("stock_backtester.data.trading_calendar.requests.get", return_value=_mock_resp(SAMPLE_PAYLOAD)):
        assert tc.is_trading_day(date(2026, 10, 9), cache_dir=tmp_path) is False   # 國慶日補假 (五)
        assert tc.is_trading_day(date(2026, 10, 5), cache_dir=tmp_path) is True    # 一般週一
        assert tc.is_trading_day(date(2026, 1, 2), cache_dir=tmp_path) is True     # 開始交易日
        assert tc.is_trading_day(date(2026, 10, 3), cache_dir=tmp_path) is False   # 週六


def test_holiday_cache_is_used(tmp_path):
    with patch("stock_backtester.data.trading_calendar.requests.get", return_value=_mock_resp(SAMPLE_PAYLOAD)) as mock_get:
        tc.is_trading_day(date(2026, 10, 9), cache_dir=tmp_path)
        tc.is_trading_day(date(2026, 10, 5), cache_dir=tmp_path)
    assert mock_get.call_count == 1
    assert (tmp_path / "twse_holidays_2026.json").exists()


def test_fetch_failure_fails_open(tmp_path):
    with patch("stock_backtester.data.trading_calendar.requests.get", side_effect=Exception("network down")):
        assert tc.is_trading_day(date(2026, 10, 9), cache_dir=tmp_path) is True
    # 失敗時不應寫入快取，下次仍會重試
    assert not (tmp_path / "twse_holidays_2026.json").exists()
