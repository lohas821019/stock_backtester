"""
盤中即時進場雷達引擎 (Live Intraday Entry Radar)

專為台股（如 0050、0052）量身打造之毫秒級盤中即時進場點監控系統。
- 支援 TWSE / TPEx MIS 官方即時撮合行情 API。
- 盤中即時偵測四大進場梯隊（右側突破、季線回踩、波段黃金拉回、極度恐慌抄底）。
- 碰價即時 Telegram 推播（30 秒內通知），杜絕收盤後或延遲推播。
- 內建每日防頻繁機制：單一標的每日推播上限 5 次 + 3 分鐘間隔冷卻，徹底杜絕洗版。
- 收盤 13:35 自動發送當日總結報表。
"""

import json
import logging
import platform
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from ..data.data_manager import DataManager
from ..notifiers.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


@dataclass
class RadarTarget:
    """單一標的之進場雷達門檻數值。"""
    symbol: str
    name: str
    roll_20_h: float          # 前 20 日最高價（右側突破目標）
    ma60: float               # 60 日季線生命線
    pullback_min_p: float     # 第一梯隊：季線回踩下緣 (MA60 * 0.98)
    pullback_max_p: float     # 第一梯隊：季線回踩上緣 (MA60 * 1.01)
    tier2_min_p: float        # 第二梯隊：波段黃金拉回下緣 (前高 * 0.90)
    tier2_max_p: float        # 第二梯隊：波段黃金拉回上緣 (前高 * 0.92)
    capitulation_p: float     # 第三梯隊：極度恐慌超跌線 (MA60 * 0.94)


@dataclass
class RealtimeQuote:
    """盤中即時撮合報價。"""
    symbol: str
    name: str
    trade_time: str
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    yesterday_close: float
    volume: int
    raw_data: dict = field(default_factory=dict)


class LiveEntryRadar:
    """
    盤中即時進場雷達監控器。
    
    支援單次檢測與常駐 Daemon 模式（盤中 09:00 ~ 13:35 持續巡檢）。
    """

    STOCK_NAMES = {
        "0050": "元大台灣50",
        "0052": "富邦科技",
        "2330": "台積電",
        "2454": "聯發科",
        "2317": "鴻海",
    }

    def __init__(
        self,
        stocks: Optional[list[str]] = None,
        notifier: Optional[TelegramNotifier] = None,
        poll_interval: int = 25,
        max_alerts_per_stock: int = 5,
        cooldown_seconds: int = 180,
        state_file: Optional[Path] = None,
        persist_state: bool = True,
    ):
        self.stocks = stocks or ["0050", "0052"]
        self.notifier = notifier
        self.poll_interval = poll_interval
        self.max_alerts_per_stock = max_alerts_per_stock
        self.cooldown_seconds = cooldown_seconds
        self.state_file = Path(state_file) if state_file else None
        self.persist_state = persist_state
        self.dm = DataManager()
        self.targets: dict[str, RadarTarget] = {}
        
        # 記錄今日每檔股票的已發送次數：{"0050": 3, "0052": 1}
        self.alert_counts: dict[str, int] = {}
        # 記錄每檔股票最後發送時間戳：{"0050": 1726900000.0}
        self.last_alert_time: dict[str, float] = {}
        # 記錄已觸發過的特定訊號事件：{(symbol, "breakout"), ...}
        self.alerted_events: set[tuple[str, str]] = set()

        if self.persist_state:
            self._load_daily_state()

    def _get_state_file_path(self) -> Path:
        if self.state_file:
            return self.state_file
        today_str = date.today().strftime("%Y%m%d")
        home_dir = Path.home() / ".stock_backtester"
        try:
            home_dir.mkdir(parents=True, exist_ok=True)
            return home_dir / f"live_radar_state_{today_str}.json"
        except Exception:
            return Path(f"/tmp/live_radar_state_{today_str}.json")

    def _load_daily_state(self) -> None:
        """載入當日狀態檔，確保重新啟動或備援任務不會重置 5 次上限計數。"""
        if not self.persist_state:
            return
        state_file = self._get_state_file_path()
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if data.get("date") == date.today().strftime("%Y-%m-%d"):
                    self.alert_counts = data.get("alert_counts", {})
                    self.last_alert_time = data.get("last_alert_time", {})
                    self.alerted_events = {tuple(x) for x in data.get("alerted_events", [])}
                    logger.info(f"成功載入今日雷達推播狀態: {self.alert_counts}")
            except Exception as e:
                logger.warning(f"讀取雷達狀態檔失敗: {e}")

    def _save_daily_state(self) -> None:
        """儲存當日推播狀態至本地快取檔。"""
        if not self.persist_state:
            return
        state_file = self._get_state_file_path()
        try:
            data = {
                "date": date.today().strftime("%Y-%m-%d"),
                "alert_counts": self.alert_counts,
                "last_alert_time": self.last_alert_time,
                "alerted_events": [list(x) for x in self.alerted_events],
            }
            state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"儲存雷達狀態檔失敗: {e}")

    def load_targets(self, as_of_date: Optional[date] = None) -> dict[str, RadarTarget]:
        """計算所有監控標的的前置雷達門檻數值（基於昨日以前之歷史數據）。"""
        ref_date = as_of_date or date.today()
        start_d = ref_date - timedelta(days=260)
        end_d = ref_date

        for stock in self.stocks:
            try:
                df = self.dm.get_ohlcv(stock, start_d, end_d)
                if df.empty:
                    logger.warning(f"無法取得 {stock} 歷史數據，跳過門檻計算")
                    continue

                # 若今日已在數據中，需排除今日以取得真正的「前 20 日高點」與「前季線」
                if len(df) > 0 and df.index[-1].date() >= ref_date:
                    hist_df = df.iloc[:-1]
                else:
                    hist_df = df

                if len(hist_df) < 20:
                    hist_df = df

                high_s = hist_df["high"]
                close_s = hist_df["close"]

                roll_20_h = float(high_s.iloc[-20:].max()) if len(high_s) >= 20 else float(high_s.max())
                ma60 = float(close_s.iloc[-60:].mean()) if len(close_s) >= 60 else float(close_s.mean())

                name = self.STOCK_NAMES.get(stock, f"{stock}")

                target = RadarTarget(
                    symbol=stock,
                    name=name,
                    roll_20_h=round(roll_20_h, 2),
                    ma60=round(ma60, 2),
                    pullback_min_p=round(ma60 * 0.98, 2),
                    pullback_max_p=round(ma60 * 1.01, 2),
                    tier2_min_p=round(roll_20_h * 0.90, 2),
                    tier2_max_p=round(roll_20_h * 0.92, 2),
                    capitulation_p=round(ma60 * 0.94, 2),
                )
                self.targets[stock] = target
                logger.info(f"[{stock} {name}] 雷達門檻: 突破 20 日高={roll_20_h}, 季線 MA60={ma60}")
            except Exception as e:
                logger.error(f"計算 {stock} 雷達門檻時失敗: {e}")

        return self.targets

    def fetch_quotes(self) -> dict[str, RealtimeQuote]:
        """向證交所 TWSE MIS 官方 API 批量抓取即時撮合行情。"""
        if not self.stocks:
            return {}

        channel_list = []
        for s in self.stocks:
            prefix = "otc" if s.startswith("6") or s.startswith("8") else "tse"
            channel_list.append(f"{prefix}_{s}.tw")

        ex_ch = "|".join(channel_list)
        twse_url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"

        quotes: dict[str, RealtimeQuote] = {}
        try:
            resp = requests.get(twse_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            items = resp.json().get("msgArray", [])
            for it in items:
                sym = it.get("c")
                if not sym:
                    continue

                z = it.get("z")
                if z == "-" or not z:
                    bids = it.get("b", "_").split("_")
                    z = bids[0] if bids and bids[0] != "" else it.get("y")

                cur_p = float(z) if z and z != "-" else float(it.get("y", 0.0))
                open_p = float(it.get("o")) if it.get("o") and it.get("o") != "-" else cur_p
                high_p = float(it.get("h")) if it.get("h") and it.get("h") != "-" else cur_p
                low_p = float(it.get("l")) if it.get("l") and it.get("l") != "-" else cur_p
                yest_p = float(it.get("y")) if it.get("y") and it.get("y") != "-" else cur_p
                vol = int(it.get("v", 0)) if it.get("v") and it.get("v") != "-" else 0
                t_str = it.get("t", datetime.now().strftime("%H:%M:%S"))
                name = it.get("n", self.STOCK_NAMES.get(sym, sym))

                quotes[sym] = RealtimeQuote(
                    symbol=sym,
                    name=name,
                    trade_time=t_str,
                    current_price=round(cur_p, 2),
                    open_price=round(open_p, 2),
                    high_price=round(high_p, 2),
                    low_price=round(low_p, 2),
                    yesterday_close=round(yest_p, 2),
                    volume=vol,
                    raw_data=it,
                )
        except Exception as e:
            logger.warning(f"TWSE MIS 報價獲取暫時失敗: {e}")

        return quotes

    def check_and_alert(self, quotes: dict[str, RealtimeQuote], send_telegram: bool = True) -> list[dict]:
        """
        核心進場訊號檢測：比對即時報價與策略門檻，碰觸立即發送急報。
        嚴格套用：
        1. 單一標的每日推播上限 5 次（滿 5 次後自動靜默，絕不重複洗版）。
        2. 推播冷卻時間（預設 3 分鐘），避免短時間內密集震盪連續推播。
        """
        triggered_signals = []
        now_ts = time.time()

        for stock, q in quotes.items():
            t = self.targets.get(stock)
            if not t:
                continue

            # 檢查是否已達每日 5 次通知上限
            current_count = self.alert_counts.get(stock, 0)
            if current_count >= self.max_alerts_per_stock:
                logger.info(f"[{stock}] 今日已達推播上限 ({self.max_alerts_per_stock} 次)，保持靜默休息")
                continue

            # 檢查冷卻時間（至少需間隔 cooldown_seconds 秒）
            last_ts = self.last_alert_time.get(stock, 0.0)
            if (now_ts - last_ts) < self.cooldown_seconds:
                continue

            bias = ((q.current_price - t.ma60) / t.ma60) * 100.0
            candidate_sig = None

            # 1. 🚀 右側突破訊號：盤中最高價或現價觸及突破門檻
            is_breakout = (q.high_price >= t.roll_20_h or q.current_price >= t.roll_20_h)
            if is_breakout and (stock, "breakout") not in self.alerted_events:
                candidate_sig = {
                    "stock": stock,
                    "name": q.name,
                    "event_key": "breakout",
                    "title": "🚀 突破 20 日高點進場門檻！",
                    "detail": f"現價 ${q.current_price:.2f}（今日最高 ${q.high_price:.2f}）已突破前高 ${t.roll_20_h:.2f}",
                    "current": q.current_price,
                    "target": t.roll_20_h,
                    "ma60": t.ma60,
                    "bias": bias,
                    "time": q.trade_time,
                }
                self.alerted_events.add((stock, "breakout"))

            # 2. 🎯 第一梯隊：季線回踩抄底區 (MA60 -2% ~ +1%)
            elif (q.low_price <= t.pullback_max_p and q.current_price >= t.pullback_min_p * 0.98) and (stock, "pullback") not in self.alerted_events:
                candidate_sig = {
                    "stock": stock,
                    "name": q.name,
                    "event_key": "pullback",
                    "title": "🎯 盤中踩入第一梯隊：季線回踩抄底區！",
                    "detail": f"今日最低 ${q.low_price:.2f} / 現價 ${q.current_price:.2f}，已進入季線守穩區 (${t.pullback_min_p:.2f} ~ ${t.pullback_max_p:.2f})",
                    "current": q.current_price,
                    "target": t.pullback_max_p,
                    "ma60": t.ma60,
                    "bias": bias,
                    "time": q.trade_time,
                }
                self.alerted_events.add((stock, "pullback"))

            # 3. 🌟 第二梯隊：波段黃金拉回區 (-8% ~ -10%)
            elif (q.low_price <= t.tier2_max_p and q.current_price >= t.tier2_min_p * 0.98) and (stock, "tier2") not in self.alerted_events:
                candidate_sig = {
                    "stock": stock,
                    "name": q.name,
                    "event_key": "tier2",
                    "title": "🌟 盤中踩入第二梯隊：波段黃金拉回區！",
                    "detail": f"今日最低 ${q.low_price:.2f} / 現價 ${q.current_price:.2f}，自高點回檔進入黃金區 (${t.tier2_min_p:.2f} ~ ${t.tier2_max_p:.2f})",
                    "current": q.current_price,
                    "target": t.tier2_max_p,
                    "ma60": t.ma60,
                    "bias": bias,
                    "time": q.trade_time,
                }
                self.alerted_events.add((stock, "tier2"))

            # 4. 🛡️ 第三梯隊：極度恐慌超跌底 (季線負乖離 <= -6%)
            elif (q.low_price <= t.capitulation_p) and (stock, "panic") not in self.alerted_events:
                candidate_sig = {
                    "stock": stock,
                    "name": q.name,
                    "event_key": "panic",
                    "title": "🛡️ 盤中觸及第三梯隊：極度恐慌超跌底！",
                    "detail": f"今日最低 ${q.low_price:.2f}，季線負乖離達 {bias:.2f}%，觸及超跌防守線 (<= ${t.capitulation_p:.2f})",
                    "current": q.current_price,
                    "target": t.capitulation_p,
                    "ma60": t.ma60,
                    "bias": bias,
                    "time": q.trade_time,
                }
                self.alerted_events.add((stock, "panic"))

            # 若觸發訊號，更新計數並發送推播
            if candidate_sig:
                new_count = current_count + 1
                self.alert_counts[stock] = new_count
                self.last_alert_time[stock] = now_ts
                candidate_sig["alert_index"] = new_count
                candidate_sig["max_alerts"] = self.max_alerts_per_stock
                self._save_daily_state()

                triggered_signals.append(candidate_sig)
                if send_telegram:
                    self._send_instant_alert(candidate_sig)

        return triggered_signals

    def _send_instant_alert(self, sig: dict) -> None:
        """發送盤中碰價即時 Telegram 通知與系統桌面通知。"""
        quote_url = f"https://tw.stock.yahoo.com/quote/{sig['stock']}.TW"
        diff = sig['current'] - sig['target']
        diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"

        count_str = f"🔔 <b>今日通知次數</b>：第 <b>{sig.get('alert_index', 1)}</b> 次 / 上限 {sig.get('max_alerts', self.max_alerts_per_stock)} 次"

        # 若已達最後一次上限，附帶防打擾提醒
        limit_note = ""
        if sig.get("alert_index", 1) >= sig.get("max_alerts", self.max_alerts_per_stock):
            limit_note = (
                f"\n\n🛑 <b>防頻繁提醒保護已啟動</b>：\n"
                f"今日 {sig['stock']} 進場急報已達 <b>{self.max_alerts_per_stock} 次上限</b>！\n"
                f"為避免盤中過於頻繁干擾，今日盤中將自動進入靜默防打擾模式。13:35 收盤將為您發送完整盤後總結！"
            )

        msg = (
            f"🚨 <b>【{sig['stock']} {sig['name']} 盤中進場急報】</b>\n\n"
            f"⚡ <b>觸發訊號：{sig['title']}</b>\n"
            f"• 最新成交價：<a href='{quote_url}'><b>${sig['current']:.2f} 元</b></a>\n"
            f"• 策略門檻價：<b>${sig['target']:.2f} 元</b> (差距 {diff_str} 元)\n"
            f"• 季線 MA60：${sig['ma60']:.2f} 元 (乖離 {sig['bias']:+.2f}%)\n"
            f"• 撮合時間：<b>{sig['time']} (盤中即時)</b>\n"
            f"• 觸發詳情：{sig['detail']}\n"
            f"• {count_str}\n\n"
            f"💡 <b>操作提醒</b>：\n"
            f"策略金額已於盤中觸碰！請檢視盤面確認量價守穩狀況，依紀律進場並落實停損防守！\n"
            f"👉 <a href='{quote_url}'>點此查看 {sig['stock']} Yahoo 即時盤面</a>"
            f"{limit_note}"
        )

        if self.notifier:
            self.notifier.send(msg)
            logger.info(f"已發送 Telegram 盤中即時通知: {sig['stock']} {sig['event_key']} (第 {sig.get('alert_index', 1)} 次)")

        # macOS 桌面即時橫幅通知
        if platform.system() == "Darwin":
            try:
                cmd = f'display notification "觸發訊號: {sig["title"]}\\n現價: ${sig["current"]:.2f}" with title "🚨 【{sig["stock"]} 盤中進場急報】"'
                subprocess.run(["osascript", "-e", cmd], check=False)
            except Exception:
                pass

    def send_closing_summary(self, quotes: dict[str, RealtimeQuote]) -> None:
        """發送每日收盤大總結推播。"""
        if not self.notifier:
            return

        today_str = date.today().strftime("%Y-%m-%d")
        lines = [f"🏁 <b>【0050 / 0052 今日收盤雷達總結 ({today_str})】</b>\n"]

        for stock, q in quotes.items():
            t = self.targets.get(stock)
            if not t:
                continue

            chg = q.current_price - q.yesterday_close
            pct = (chg / q.yesterday_close) * 100.0 if q.yesterday_close > 0 else 0.0
            sign = "+" if chg >= 0 else ""
            color = "🟢" if chg >= 0 else "🔴"

            quote_url = f"https://tw.stock.yahoo.com/quote/{stock}.TW"
            dist_bo = t.roll_20_h - q.current_price
            bo_status = "🚨 <b>今日已突破！</b>" if q.high_price >= t.roll_20_h else f"差 {dist_bo:+.2f} 元"
            alert_cnt = self.alert_counts.get(stock, 0)

            lines.append(
                f"📊 <b>{stock} {q.name}</b>\n"
                f"• 今日收盤：<a href='{quote_url}'><b>${q.current_price:.2f} 元</b></a> ({color} {sign}{chg:.2f}, {sign}{pct:.2f}%)\n"
                f"• 盤中區間：最高 ${q.high_price:.2f} / 最低 ${q.low_price:.2f}\n"
                f"• 🚀 20日突破線：<b>${t.roll_20_h:.2f} 元</b> (現況: {bo_status})\n"
                f"• 🎯 季線回踩區：${t.pullback_min_p:.2f} ~ ${t.pullback_max_p:.2f} 元 (季線 ${t.ma60:.2f})\n"
                f"• 🌟 黃金拉回區：${t.tier2_min_p:.2f} ~ ${t.tier2_max_p:.2f} 元\n"
                f"• 🔔 盤中提醒次數：共發送 {alert_cnt} 次急報\n"
            )

        lines.append("☕ <b>監控狀態</b>：今日交易已結束，明日開盤 08:50 將自動恢復即時盯盤！")
        summary_msg = "\n".join(lines)
        self.notifier.send(summary_msg)
        logger.info("已發送今日收盤總結推播")

    def run_daemon(self, max_duration_hours: float = 5.0) -> None:
        """
        常駐守護執行緒：在台股交易時段 (08:58 ~ 13:35) 每隔 poll_interval 秒即時巡檢。
        """
        logger.info(f"啟動盤中實時雷達守護行程 (標的: {self.stocks}, 間隔: {self.poll_interval}s, 上限: {self.max_alerts_per_stock}次)")
        self.load_targets()

        start_time = time.time()
        max_seconds = max_duration_hours * 3600
        summary_sent = False

        while True:
            now = datetime.now()
            cur_time_int = now.hour * 100 + now.minute

            # 若已過 13:35（收盤結算時間）
            if cur_time_int >= 1335:
                quotes = self.fetch_quotes()
                if not summary_sent and quotes:
                    self.send_closing_summary(quotes)
                    summary_sent = True
                logger.info("已過收盤時間 13:35，守護行程正常結束。")
                break

            # 若未到 08:58（盤前撮合前），稍作等待
            if cur_time_int < 858:
                time.sleep(15)
                continue

            # 盤中交易時段 (08:58 ~ 13:35)：即時抓取撮合並檢測碰價
            quotes = self.fetch_quotes()
            if quotes:
                self.check_and_alert(quotes, send_telegram=True)

            # 超時保護
            if (time.time() - start_time) > max_seconds:
                logger.info("達到單次執行最大時間限制，守護行程結束。")
                break

            time.sleep(self.poll_interval)
