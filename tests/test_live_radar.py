import pytest
from unittest.mock import MagicMock, patch
from stock_backtester.scanner.live_radar import LiveEntryRadar, RadarTarget, RealtimeQuote


def test_live_radar_check_and_alert_breakout():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    quotes = {
        "0050": RealtimeQuote(
            symbol="0050",
            name="元大台灣50",
            trade_time="10:15:00",
            current_price=111.35,
            open_price=109.90,
            high_price=111.45,
            low_price=109.85,
            yesterday_close=109.85,
            volume=50000,
        )
    }

    signals = radar.check_and_alert(quotes, send_telegram=True)
    assert len(signals) == 1
    assert signals[0]["event_key"] == "breakout"
    assert "突破" in signals[0]["title"]
    assert notifier.send.called

    # Test de-duplication: running check again on the same day should not alert again
    notifier.reset_mock()
    signals2 = radar.check_and_alert(quotes, send_telegram=True)
    assert len(signals2) == 0
    assert not notifier.send.called


def test_live_radar_check_pullback():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    # Price touches pullback zone (low <= 106.01)
    quotes = {
        "0050": RealtimeQuote(
            symbol="0050",
            name="元大台灣50",
            trade_time="09:30:00",
            current_price=105.50,
            open_price=106.00,
            high_price=106.20,
            low_price=105.10,
            yesterday_close=106.50,
            volume=30000,
        )
    }

    signals = radar.check_and_alert(quotes, send_telegram=True)
    assert len(signals) == 1
    assert signals[0]["event_key"] == "pullback"
    assert "季線回踩" in signals[0]["title"]
    assert notifier.send.called


def test_live_radar_max_alerts_cap():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, max_alerts_per_stock=5, cooldown_seconds=0, persist_state=False)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    quotes = {
        "0050": RealtimeQuote(
            symbol="0050",
            name="元大台灣50",
            trade_time="10:00:00",
            current_price=111.0,
            open_price=109.9,
            high_price=111.5,
            low_price=109.8,
            yesterday_close=109.8,
            volume=10000,
        )
    }

    # Simulate 5 alerts by resetting alerted_events
    for i in range(1, 6):
        radar.alerted_events.clear()
        sigs = radar.check_and_alert(quotes, send_telegram=True)
        assert len(sigs) == 1
        assert sigs[0]["alert_index"] == i

    assert radar.alert_counts["0050"] == 5

    # 6th attempt should be blocked and not sent
    radar.alerted_events.clear()
    sigs6 = radar.check_and_alert(quotes, send_telegram=True)
    assert len(sigs6) == 0


def test_live_radar_state_persistence(tmp_path):
    state_file = tmp_path / "radar_state.json"
    notifier = MagicMock()
    radar1 = LiveEntryRadar(stocks=["0050"], notifier=notifier, cooldown_seconds=0, state_file=state_file, persist_state=True)
    radar1.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    quotes = {
        "0050": RealtimeQuote(
            symbol="0050",
            name="元大台灣50",
            trade_time="10:00:00",
            current_price=111.0,
            open_price=109.9,
            high_price=111.5,
            low_price=109.8,
            yesterday_close=109.8,
            volume=10000,
        )
    }

    # send_telegram=False → 純預覽模式：不更新計數、不儲存狀態、不消耗 alerted_events
    radar1.check_and_alert(quotes, send_telegram=False)
    assert "0050" not in radar1.alert_counts  # 預覽模式不更新計數
    assert ("0050", "breakout") not in radar1.alerted_events  # 預覽模式不標記事件
    assert not state_file.exists()  # 預覽模式不寫狀態檔

    # send_telegram=True → 正式發送：更新計數、儲存狀態、標記事件
    radar1.check_and_alert(quotes, send_telegram=True)
    assert radar1.alert_counts["0050"] == 1
    assert ("0050", "breakout") in radar1.alerted_events
    assert state_file.exists()

    # Create new radar instance pointing to the same state file
    radar2 = LiveEntryRadar(stocks=["0050"], notifier=notifier, cooldown_seconds=0, state_file=state_file, persist_state=True)
    assert radar2.alert_counts["0050"] == 1
    assert ("0050", "breakout") in radar2.alerted_events


def test_live_radar_holiday_stale_data_filter():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    # Stale quote from an earlier date (e.g., holiday or weekend)
    quotes = {
        "0050": RealtimeQuote(
            symbol="0050",
            name="元大台灣50",
            trade_time="13:30:00",
            current_price=111.50,
            open_price=110.00,
            high_price=112.00,
            low_price=109.80,
            yesterday_close=109.80,
            volume=50000,
            quote_date="20200101",  # Past date, not today
        )
    }

    # Should be filtered out and not send any false alert
    signals = radar.check_and_alert(quotes, send_telegram=True, filter_holiday=True)
    assert len(signals) == 0
    assert not notifier.send.called


def test_live_radar_stop_loss_trigger():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    # Price breaks below MA60 by > 2% (current_price < 104.96 * 0.98 = 102.86)
    quotes = {
        "0050": RealtimeQuote(
            symbol="0050",
            name="元大台灣50",
            trade_time="11:30:00",
            current_price=102.00,
            open_price=103.50,
            high_price=103.80,
            low_price=101.80,
            yesterday_close=104.00,
            volume=40000,
        )
    }

    signals = radar.check_and_alert(quotes, send_telegram=True)
    assert len(signals) == 1
    assert signals[0]["event_key"] == "stop_loss_ma60"
    assert signals[0].get("is_stop_loss") is True
    assert "跌破 60 日季線生命線" in signals[0]["title"]
    assert notifier.send.called


def test_live_radar_morning_heartbeat_silent():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    radar.send_morning_heartbeat()
    assert notifier.send.called
    args, kwargs = notifier.send.call_args
    assert kwargs.get("silent") is True
    assert "09:00 盤中實時雷達上線打卡" in args[0]


def test_telegram_notifier_silent_payload():
    from stock_backtester.notifiers.telegram_notifier import TelegramNotifier
    notifier = TelegramNotifier(token="fake:token", chat_id="123456")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        notifier.send("測試訊息", silent=True)
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["disable_notification"] is True


def test_live_radar_startup_notification_silent():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )

    radar.send_startup_notification()
    assert notifier.send.called
    args, kwargs = notifier.send.call_args
    assert kwargs.get("silent") is True
    assert "台股實時雷達守護行程已喚醒" in args[0]
    assert "準備盯盤" in args[0]





def _make_radar_with_target(notifier):
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier, persist_state=False, cooldown_seconds=0)
    radar.targets["0050"] = RadarTarget(
        symbol="0050",
        name="元大台灣50",
        roll_20_h=110.75,
        ma60=104.96,
        pullback_min_p=102.86,
        pullback_max_p=106.01,
        tier2_min_p=99.67,
        tier2_max_p=101.89,
        capitulation_p=98.66,
    )
    return radar


def _quote():
    return {
        "0050": RealtimeQuote(
            symbol="0050", name="元大台灣50", trade_time="13:30:00",
            current_price=108.0, open_price=107.0, high_price=108.5,
            low_price=106.8, yesterday_close=107.0, volume=10000,
        )
    }


def test_morning_heartbeat_on_time_has_no_delay_warning():
    from datetime import datetime
    from stock_backtester.scanner.live_radar import TW_TZ

    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    radar.send_morning_heartbeat(now=datetime(2026, 10, 5, 9, 2, 0, tzinfo=TW_TZ))
    msg = notifier.send.call_args[0][0]
    assert "實際上線時間：<b>09:02:00</b>" in msg
    assert "排程延遲" not in msg


def test_morning_heartbeat_late_shows_delay_warning():
    from datetime import datetime
    from stock_backtester.scanner.live_radar import TW_TZ

    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    radar.send_morning_heartbeat(now=datetime(2026, 10, 5, 11, 30, 0, tzinfo=TW_TZ))
    msg = notifier.send.call_args[0][0]
    assert "排程延遲約 150 分鐘" in msg


def test_run_once_closing_summary_flags_missed_radar():
    from datetime import datetime
    from stock_backtester.scanner.live_radar import TW_TZ

    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    fake_now = datetime(2026, 10, 5, 14, 24, 0, tzinfo=TW_TZ)
    with patch("stock_backtester.scanner.live_radar.datetime") as mock_dt, \
         patch("stock_backtester.scanner.live_radar.is_trading_day", return_value=True), \
         patch.object(radar, "fetch_quotes", return_value=_quote()):
        mock_dt.now.return_value = fake_now
        radar.run_once()

    msg = notifier.send.call_args[0][0]
    assert "今日盤中雷達未能上線" in msg
    assert radar.daily_flags.get("summary_sent") is True


def test_run_once_closing_summary_normal_when_heartbeat_sent():
    from datetime import datetime
    from stock_backtester.scanner.live_radar import TW_TZ

    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    radar.daily_flags["heartbeat_sent"] = True
    fake_now = datetime(2026, 10, 5, 13, 40, 0, tzinfo=TW_TZ)
    with patch("stock_backtester.scanner.live_radar.datetime") as mock_dt, \
         patch("stock_backtester.scanner.live_radar.is_trading_day", return_value=True), \
         patch.object(radar, "fetch_quotes", return_value=_quote()):
        mock_dt.now.return_value = fake_now
        radar.run_once()

    msg = notifier.send.call_args[0][0]
    assert "今日盤中雷達未能上線" not in msg
    assert "收盤雷達總結" in msg


def _assert_telegram_html_safe(msg: str):
    """模擬 Telegram HTML parse_mode：只允許 b / a 標籤，其餘 '<' 必須已跳脫。"""
    import re
    stripped = re.sub(r"</?b>|<a href='[^']*'>|</a>", "", msg)
    assert "<" not in stripped, f"未跳脫的 '<' 會導致 Telegram 400: {stripped}"


def test_morning_heartbeat_is_telegram_html_safe():
    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    radar.send_morning_heartbeat()
    _assert_telegram_html_safe(notifier.send.call_args[0][0])


def test_panic_alert_is_telegram_html_safe():
    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    quotes = {
        "0050": RealtimeQuote(
            symbol="0050", name="元大台灣50", trade_time="10:00:00",
            current_price=98.0, open_price=100.0, high_price=100.0,
            low_price=97.5, yesterday_close=100.0, volume=10000,
        )
    }
    radar.check_and_alert(quotes, send_telegram=True)
    assert notifier.send.called
    for call in notifier.send.call_args_list:
        _assert_telegram_html_safe(call[0][0])


def test_run_once_skips_everything_on_holiday():
    from datetime import datetime
    from stock_backtester.scanner.live_radar import TW_TZ

    notifier = MagicMock()
    radar = _make_radar_with_target(notifier)
    fake_now = datetime(2026, 10, 9, 13, 40, 0, tzinfo=TW_TZ)  # 國慶日補假
    with patch("stock_backtester.scanner.live_radar.datetime") as mock_dt, \
         patch("stock_backtester.scanner.live_radar.is_trading_day", return_value=False), \
         patch.object(radar, "fetch_quotes", return_value=_quote()) as mock_fetch:
        mock_dt.now.return_value = fake_now
        result = radar.run_once()

    assert result == []
    assert not notifier.send.called
    assert not mock_fetch.called
