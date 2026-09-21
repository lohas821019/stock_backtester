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

    radar1.check_and_alert(quotes, send_telegram=False)
    assert radar1.alert_counts["0050"] == 1
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



