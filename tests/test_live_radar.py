import pytest
from unittest.mock import MagicMock, patch
from stock_backtester.scanner.live_radar import LiveEntryRadar, RadarTarget, RealtimeQuote


def test_live_radar_check_and_alert_breakout():
    notifier = MagicMock()
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier)
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
    radar = LiveEntryRadar(stocks=["0050"], notifier=notifier)
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
