"""
掃描配置檔

設定每日掃描要追蹤的股票清單與策略組合。
"""

from dataclasses import dataclass, field
from ..data.constituents import TAIWAN_50_STOCKS


@dataclass
class StockScanConfig:
    """單一股票的掃描設定。"""
    symbol: str                    # 股票代號，如 "2330"
    market: str = "auto"           # "auto" / "tw_listed" / "tw_otc" / "us"
    name: str = ""                 # 自訂顯示名稱，如 "台積電"
    strategies: list[str] = field(default_factory=lambda: ["weekly_kd_rsi"])
    # 每個策略的自訂參數（若不填則使用預設值）
    strategy_params: dict[str, dict] = field(default_factory=dict)
    # 計算訊號所需的歷史資料天數（週線指標建議 120 天以上）
    lookback_days: int = 120


def build_taiwan_50_configs(strategies: list[str] = None) -> list[StockScanConfig]:
    """快捷產生 0050 及全部 50 檔成分股的掃描設定清單。"""
    if strategies is None:
        strategies = ["weekly_kd_rsi", "ma_cross"]

    return [
        StockScanConfig(
            symbol=item["symbol"],
            name=item["name"],
            market="tw_listed",
            strategies=strategies,
            lookback_days=150,  # 確保足夠週數計算週 KD (9週) 及週 RSI (14週)
        )
        for item in TAIWAN_50_STOCKS
    ]


# ══════════════════════════════════════════════════════════════════════
# 掃描清單設定：
# 可選 1: 僅掃描自訂核心重點持股
# 可選 2: 啟用整組 0050 成分股 (使用 build_taiwan_50_configs())
# ══════════════════════════════════════════════════════════════════════

# 預設包含 0050 及全套 50 檔成分股！
SCAN_STOCKS: list[StockScanConfig] = build_taiwan_50_configs(
    strategies=["weekly_kd_rsi"]
)

# ── 通知條件設定 ──────────────────────────────────────────────────────
# 訊號一致性門檻：同一股票有幾個策略發出買進才通知
# 1 = 任一策略買進就通知，2 = 至少 2 個策略同時買進才通知
MIN_AGREE_STRATEGIES: int = 1

# 是否在「無訊號」時也發送每日摘要（每日健康確認）
SEND_DAILY_SUMMARY: bool = True
