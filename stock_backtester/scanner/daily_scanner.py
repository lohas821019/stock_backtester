"""
每日入場點掃描器 DailyScanner

邏輯：
    1. 讀取 scan_config.py 的股票清單
    2. 對每支股票，抓取近 N 天的 OHLCV（有快取就不重複下載）
    3. 跑每個指定策略，取「今日」的訊號值
    4. 若訊號 == 1（買進），加入候選清單
    5. 達到 MIN_AGREE_STRATEGIES 門檻，即透過 Telegram 通知
    6. 最後發送每日掃描摘要
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from ..data.data_manager import DataManager
from ..strategies import get_strategy
from ..notifiers.telegram_notifier import TelegramNotifier
from .scan_config import StockScanConfig, MIN_AGREE_STRATEGIES, SEND_DAILY_SUMMARY

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """單一股票 × 策略的訊號結果。"""
    symbol: str
    name: str
    strategy_name: str
    signal: int          # 1=買進 / -1=賣出 / 0=持平
    today_close: float
    scan_date: date


@dataclass
class ScanSummary:
    """今日掃描摘要。"""
    scan_date: date
    total_scanned: int
    buy_signals: list[SignalResult]
    errors: list[str]


class DailyScanner:
    """
    每日入場點掃描器。

    使用範例：
        scanner = DailyScanner(notifier=TelegramNotifier(...))
        scanner.run()
    """

    def __init__(
        self,
        notifier: TelegramNotifier,
        data_manager: DataManager | None = None,
        scan_date: date | None = None,
    ):
        """
        Args:
            notifier:     Telegram 通知器
            data_manager: 資料管理器（None 則自動建立）
            scan_date:    掃描日期（None 則為今天）
        """
        self._notifier = notifier
        self._dm = data_manager or DataManager()
        self._scan_date = scan_date or date.today()

    def run(self, stocks: list[StockScanConfig]) -> ScanSummary:
        """
        執行每日掃描。

        Args:
            stocks: 要掃描的股票設定清單（來自 scan_config.py）

        Returns:
            ScanSummary
        """
        logger.info("[Scanner] 開始掃描，日期: %s，共 %d 支股票", self._scan_date, len(stocks))

        all_results: list[SignalResult] = []
        errors: list[str] = []

        for cfg in stocks:
            try:
                results = self._scan_one(cfg)
                all_results.extend(results)
            except Exception as e:
                msg = f"{cfg.symbol}（{cfg.name}）掃描失敗：{e}"
                logger.error("[Scanner] %s", msg)
                errors.append(msg)

        # 篩出買進訊號
        buy_signals = [r for r in all_results if r.signal == 1]

        # 依股票聚合：計算每股有幾個策略同時看多
        buy_by_symbol: dict[str, list[SignalResult]] = {}
        for r in buy_signals:
            buy_by_symbol.setdefault(r.symbol, []).append(r)

        # 發送個別通知（符合門檻的才通知）
        notified_symbols: list[str] = []
        for symbol, results in buy_by_symbol.items():
            if len(results) >= MIN_AGREE_STRATEGIES:
                self._notify_buy(results)
                notified_symbols.append(symbol)

        summary = ScanSummary(
            scan_date=self._scan_date,
            total_scanned=len(stocks),
            buy_signals=buy_signals,
            errors=errors,
        )

        # 每日摘要通知
        if SEND_DAILY_SUMMARY:
            self._notify_summary(summary, notified_symbols)

        logger.info(
            "[Scanner] 掃描完成：買進訊號 %d 個，通知 %d 支股票",
            len(buy_signals), len(notified_symbols),
        )
        return summary

    def _scan_one(self, cfg: StockScanConfig) -> list[SignalResult]:
        """掃描單一股票，回傳所有策略的訊號結果。"""
        end = self._scan_date
        start = end - timedelta(days=cfg.lookback_days + 30)  # 多抓一些以確保指標穩定

        logger.info("[Scanner] 掃描 %s（%s）...", cfg.symbol, cfg.name)
        df = self._dm.get_ohlcv(cfg.symbol, start, end, market=cfg.market)

        if df.empty:
            raise ValueError(f"無法取得 {cfg.symbol} 的資料")

        # 今日（最後一個交易日）的收盤價
        today_close = float(df["close"].iloc[-1])
        results = []

        for strategy_name in cfg.strategies:
            try:
                StratClass = get_strategy(strategy_name)
                params = cfg.strategy_params.get(strategy_name, {})
                strategy = StratClass(**params)

                signals = strategy.generate_signals(df)
                today_signal = int(signals.iloc[-1])

                results.append(SignalResult(
                    symbol=cfg.symbol,
                    name=cfg.name or cfg.symbol,
                    strategy_name=strategy_name,
                    signal=today_signal,
                    today_close=today_close,
                    scan_date=self._scan_date,
                ))

                signal_emoji = {1: "🟢", -1: "🔴", 0: "⚪"}.get(today_signal, "⚪")
                logger.info(
                    "[Scanner]   %s %s[%s] → 訊號: %s%d",
                    cfg.symbol, strategy_name, params, signal_emoji, today_signal,
                )

            except Exception as e:
                logger.warning("[Scanner] %s / %s 計算失敗: %s", cfg.symbol, strategy_name, e)

        return results

    def _notify_buy(self, results: list[SignalResult]) -> None:
        """發送單一股票的買進通知。"""
        r = results[0]
        strategies_str = "\n".join(
            f"  • <b>{x.strategy_name}</b> → 🟢 買進"
            for x in results
        )

        msg = (
            f"🚀 <b>入場訊號！</b>\n"
            f"\n"
            f"📌 <b>{r.name}（{r.symbol}）</b>\n"
            f"📅 日期：{r.scan_date}\n"
            f"💵 收盤價：<b>{r.today_close:,.2f}</b>\n"
            f"\n"
            f"策略訊號：\n"
            f"{strategies_str}\n"
            f"\n"
            f"⚠️ 此為策略訊號，非投資建議，請自行評估風險。"
        )
        self._notifier.send(msg)

    def _notify_summary(self, summary: ScanSummary, notified: list[str]) -> None:
        """發送每日掃描摘要。"""
        if summary.buy_signals:
            # 有訊號才列出
            buy_lines = []
            seen = set()
            for r in summary.buy_signals:
                key = (r.symbol, r.strategy_name)
                if key not in seen:
                    seen.add(key)
                    buy_lines.append(
                        f"  🟢 {r.name}（{r.symbol}）— {r.strategy_name}"
                    )
            buy_section = "\n".join(buy_lines)
        else:
            buy_section = "  ⚪ 今日無買進訊號"

        error_section = ""
        if summary.errors:
            error_section = "\n\n⚠️ 錯誤：\n" + "\n".join(
                f"  • {e}" for e in summary.errors
            )

        msg = (
            f"📊 <b>每日掃描摘要</b> — {summary.scan_date}\n"
            f"\n"
            f"掃描股票：{summary.total_scanned} 支\n"
            f"買進訊號：{len(set(r.symbol for r in summary.buy_signals))} 支\n"
            f"\n"
            f"<b>今日訊號：</b>\n"
            f"{buy_section}"
            f"{error_section}"
        )
        self._notifier.send(msg)
