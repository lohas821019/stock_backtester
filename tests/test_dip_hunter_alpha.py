import pandas as pd
import numpy as np
import pytest
from stock_backtester.strategies.dip_hunter_alpha import DipHunterAlphaStrategy


def _make_dummy_ohlcv(n: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    base = 100.0
    prices = [base]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.01)))
    prices = np.array(prices)
    df = pd.DataFrame(
        {
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1000, 10000, n).astype(float),
        },
        index=dates,
    )
    return df


def test_dip_hunter_alpha_basic():
    df = _make_dummy_ohlcv(120)
    strat = DipHunterAlphaStrategy()
    sig = strat.generate_signals(df)
    assert isinstance(sig, pd.Series)
    assert len(sig) == len(df)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_dip_hunter_alpha_pullback_entry():
    # 構造一個回踩季線守穩的數據
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    # 均價在 100 附近緩步上升
    prices = [100.0 + i * 0.1 for i in range(80)]
    df = pd.DataFrame(
        {
            "open": [p - 0.2 for p in prices],
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
            "volume": [1000.0] * 80,
        },
        index=dates,
    )
    # 在第 70 天人工製造回踩季線且收紅 K
    ma = pd.Series(prices).rolling(60).mean().iloc[70]
    df.iloc[70, df.columns.get_loc("open")] = ma - 0.5
    df.iloc[70, df.columns.get_loc("close")] = ma + 0.2
    
    strat = DipHunterAlphaStrategy(enter_on_start=False)
    sig = strat.generate_signals(df)
    assert (sig == 1).any()
