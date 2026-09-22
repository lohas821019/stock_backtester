"""
命令列介面（CLI）

使用方式：
    # 下載台積電 2024 年資料
    python -m stock_backtester.cli fetch --stock 2330 --start 2024-01-01

    # 執行回測
    python -m stock_backtester.cli backtest --stock 2330 --strategy ma_cross --start 2023-01-01

    # 列出所有策略
    python -m stock_backtester.cli list-strategies

    # 執行今日入場點掃描並透過 Telegram 通知
    python -m stock_backtester.cli scan

    # 測試 Telegram 通知是否正常
    python -m stock_backtester.cli test-notify
"""


import logging
from datetime import date, datetime

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, default=False, help="顯示詳細 log")
@click.pass_context
def main(ctx, verbose):
    """📈 股票回測系統 - Stock Backtester"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


@main.command("list-strategies")
def cmd_list_strategies():
    """列出所有可用的回測策略。"""
    from stock_backtester.strategies import list_strategies

    strategies = list_strategies()

    table = Table(title="📋 可用策略清單", show_header=True, header_style="bold cyan")
    table.add_column("策略名稱", style="green", no_wrap=True)
    table.add_column("類別名稱", style="dim")
    table.add_column("說明")

    for s in strategies:
        table.add_row(s["name"], s["class"], s["description"])

    console.print(table)
    console.print(
        f"\n[dim]共 {len(strategies)} 個策略。新增策略：在 strategies/ 目錄下建立新 .py 檔。[/dim]"
    )


@main.command("fetch")
@click.option("--stock", "-s", required=True, help="股票代號（如 2330、TSM、2330.TW）")
@click.option("--start", required=True, help="開始日期 YYYY-MM-DD")
@click.option("--end", default=None, help="結束日期 YYYY-MM-DD（預設：今天）")
@click.option("--interval", default="1d", help="資料粒度：1d / 1min / 5min / 15min / 60min")
@click.option("--market", default="auto", help="市場：auto / tw_listed / tw_otc / us")
@click.pass_context
def cmd_fetch(ctx, stock, start, end, interval, market):
    """下載並快取股票 OHLCV 資料。"""
    from stock_backtester.data.data_manager import DataManager

    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else date.today()

    console.print(
        f"[bold]下載資料：[/bold] {stock} | {start_date} ~ {end_date} | {interval}"
    )

    dm = DataManager()
    with console.status(f"[cyan]正在下載 {stock} 資料...[/cyan]"):
        df = dm.get_ohlcv(stock, start_date, end_date, interval=interval, market=market)

    if df.empty:
        console.print("[red]❌ 無法取得資料，請確認股票代號與日期範圍。[/red]")
        raise click.Abort()

    console.print(f"[green]✅ 成功取得 {len(df)} 筆資料[/green]")
    console.print(df.tail(5).to_string())


@main.command("backtest")
@click.option("--stock", "-s", required=True, help="股票代號")
@click.option("--strategy", "-st", required=True, help="策略名稱（使用 list-strategies 查詢）")
@click.option("--start", required=True, help="開始日期 YYYY-MM-DD")
@click.option("--end", default=None, help="結束日期 YYYY-MM-DD（預設：今天）")
@click.option("--capital", default=1_000_000, show_default=True, help="初始資金（元）")
@click.option("--interval", default="1d", help="資料粒度")
@click.option("--market", default="auto", help="市場：auto / tw_listed / tw_otc / us")
@click.option("--param", "-p", multiple=True, help="策略參數 key=value（可重複）")
@click.option("--plot", is_flag=True, default=False, help="顯示績效圖表")
@click.pass_context
def cmd_backtest(ctx, stock, strategy, start, end, capital, interval, market, param, plot):
    """執行回測並顯示績效報告。"""
    from stock_backtester.data.data_manager import DataManager
    from stock_backtester.strategies import get_strategy
    from stock_backtester.engine.backtest_engine import BacktestEngine
    from stock_backtester.analysis.performance import PerformanceAnalyzer

    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else date.today()

    # 解析策略參數
    strategy_params = {}
    for p in param:
        if "=" not in p:
            console.print(f"[red]參數格式錯誤: {p}（應為 key=value）[/red]")
            raise click.Abort()
        k, v = p.split("=", 1)
        # 嘗試數值轉換
        try:
            strategy_params[k] = int(v)
        except ValueError:
            try:
                strategy_params[k] = float(v)
            except ValueError:
                strategy_params[k] = v

    # 載入策略
    try:
        StrategyClass = get_strategy(strategy)
        strat = StrategyClass(**strategy_params)
    except KeyError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ 策略初始化失敗: {e}[/red]")
        raise click.Abort()

    # 下載資料
    console.print(
        f"[bold]回測：[/bold] {stock} | {strategy} | {start_date} ~ {end_date}"
    )
    dm = DataManager()
    with console.status("[cyan]下載資料中...[/cyan]"):
        df = dm.get_ohlcv(stock, start_date, end_date, interval=interval, market=market)

    if df.empty:
        console.print("[red]❌ 無法取得資料[/red]")
        raise click.Abort()

    # 執行回測
    engine = BacktestEngine(initial_capital=float(capital))
    with console.status("[cyan]回測中...[/cyan]"):
        result = engine.run(df, strat, symbol=stock)

    # 績效分析
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.analyze(result)
    report = analyzer.format_report(metrics, result)
    console.print(report)

    if plot:
        _show_plot(result)


def _show_plot(result) -> None:
    """顯示互動式績效圖表（需要 plotly）。"""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=["資金曲線", "股票收盤價"],
            row_heights=[0.6, 0.4],
        )

        # 資金曲線
        fig.add_trace(
            go.Scatter(
                x=result.equity_curve.index,
                y=result.equity_curve.values,
                name="資金曲線",
                line={"color": "royalblue"},
            ),
            row=1, col=1,
        )

        # 買賣點標記
        buy_signals  = result.signals[result.signals == 1]
        sell_signals = result.signals[result.signals == -1]

        fig.add_trace(
            go.Scatter(
                x=buy_signals.index,
                y=result.data.loc[buy_signals.index, "close"],
                mode="markers",
                name="買進",
                marker={"symbol": "triangle-up", "color": "green", "size": 10},
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sell_signals.index,
                y=result.data.loc[sell_signals.index, "close"],
                mode="markers",
                name="賣出",
                marker={"symbol": "triangle-down", "color": "red", "size": 10},
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=result.data.index,
                y=result.data["close"],
                name="收盤價",
                line={"color": "gray", "width": 1},
            ),
            row=2, col=1,
        )

        fig.update_layout(
            title=f"{result.symbol} | {result.strategy_name} 回測結果",
            height=700,
        )
        fig.show()

    except ImportError:
        console.print("[yellow]提示：安裝 plotly 以顯示圖表：pip install plotly[/yellow]")



def _load_env_to_os() -> tuple[str, str]:
    """從 .env 讀取 Telegram 憑證，回傳 (token, chat_id)。"""
    import os
    from pathlib import Path

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    return token, chat_id


@main.command("test-notify")
@click.pass_context
def cmd_test_notify(ctx):
    """測試 Telegram 通知連線是否正常。"""
    from stock_backtester.notifiers.telegram_notifier import TelegramNotifier

    token, chat_id = _load_env_to_os()

    if not token or token == "your_bot_token_here":
        console.print("[red]❌ 請先在 .env 填入 TELEGRAM_BOT_TOKEN[/red]")
        console.print("[dim]複製 .env.example 為 .env 並填入憑證[/dim]")
        raise click.Abort()

    if not chat_id or chat_id == "your_chat_id_here":
        console.print("[red]❌ 請先在 .env 填入 TELEGRAM_CHAT_ID[/red]")
        raise click.Abort()

    notifier = TelegramNotifier(token=token, chat_id=chat_id)

    console.print("[cyan]測試 Bot 連線...[/cyan]")
    if not notifier.test_connection():
        console.print("[red]❌ Bot 連線失敗，請確認 TOKEN 是否正確[/red]")
        raise click.Abort()

    console.print("[cyan]發送測試訊息...[/cyan]")
    ok = notifier.send(
        "✅ <b>Stock Backtester 通知測試</b>\n\n"
        "Telegram 通知已設定成功！\n"
        "每日掃描結果將會在這裡顯示。"
    )
    if ok:
        console.print("[green]✅ 測試訊息發送成功！請查看 Telegram。[/green]")
    else:
        console.print("[red]❌ 訊息發送失敗，請確認 CHAT_ID 是否正確[/red]")


@main.command("scan")
@click.option("--date", "scan_date_str", default=None, help="掃描日期 YYYY-MM-DD（預設：今天）")
@click.option("--dry-run", is_flag=True, default=False, help="只顯示訊號，不發送 Telegram 通知")
@click.pass_context
def cmd_scan(ctx, scan_date_str, dry_run):
    """執行今日入場點掃描，有買進訊號時透過 Telegram 通知。"""
    from datetime import datetime as dt
    from stock_backtester.notifiers.telegram_notifier import TelegramNotifier
    from stock_backtester.scanner.daily_scanner import DailyScanner
    from stock_backtester.scanner.scan_config import SCAN_STOCKS

    scan_date = (
        dt.strptime(scan_date_str, "%Y-%m-%d").date()
        if scan_date_str else date.today()
    )

    if dry_run:
        console.print(f"[yellow]🔍 Dry-run 模式：只顯示訊號，不發送通知[/yellow]")

    token, chat_id = _load_env_to_os()

    if not dry_run and (not token or token == "your_bot_token_here"):
        console.print("[red]❌ 未設定 TELEGRAM_BOT_TOKEN，請先執行：[/red]")
        console.print("[dim]  python -m stock_backtester.cli test-notify[/dim]")
        raise click.Abort()

    # dry-run 模式使用假的 notifier（只印到 console）
    class _DryRunNotifier:
        def send(self, text, **_):
            # 去除 HTML tags 再顯示
            import re
            clean = re.sub(r"<[^>]+>", "", text)
            console.print(f"\n[dim]── Telegram 訊息預覽 ──[/dim]\n{clean}")
            return True
        def test_connection(self): return True

    notifier = _DryRunNotifier() if dry_run else TelegramNotifier(token=token, chat_id=chat_id)

    if not dry_run and not notifier.test_connection():
        console.print("[red]❌ Telegram Bot 連線失敗[/red]")
        raise click.Abort()

    console.print(f"[bold]📡 開始掃描 {len(SCAN_STOCKS)} 支股票...[/bold] 日期：{scan_date}")

    with console.status("[cyan]掃描中...[/cyan]"):
        scanner = DailyScanner(notifier=notifier, scan_date=scan_date)
        summary = scanner.run(SCAN_STOCKS)

    # 顯示結果表格
    from rich.table import Table
    table = Table(title=f"📊 掃描結果 — {summary.scan_date}", show_header=True, header_style="bold cyan")
    table.add_column("股票", style="bold")
    table.add_column("策略")
    table.add_column("訊號", justify="center")
    table.add_column("收盤價", justify="right")

    signal_map = {1: "[green]🟢 買進[/green]", -1: "[red]🔴 賣出[/red]", 0: "[dim]⚪ 持平[/dim]"}

    # 收集所有訊號（從 scanner 內部重跑一次太浪費，改為呈現 buy_signals）
    buy_set = {(r.symbol, r.strategy_name) for r in summary.buy_signals}
    for r in summary.buy_signals:
        table.add_row(
            f"{r.name}（{r.symbol}）",
            r.strategy_name,
            signal_map.get(r.signal, "?"),
            f"{r.today_close:,.2f}",
        )

    if summary.buy_signals:
        console.print(table)
    else:
        console.print("[dim]今日無買進訊號[/dim]")

    if summary.errors:
        console.print(f"\n[yellow]⚠️ {len(summary.errors)} 個股票發生錯誤：[/yellow]")
        for err in summary.errors:
            console.print(f"  [red]{err}[/red]")


@main.command("watch-entry")
@click.option("--stock", "-s", default="0050", help="股票代號（預設：0050）")
@click.option("--notify", is_flag=True, default=False, help="若滿足進場條件則發送 Telegram 通知")
@click.option("--summary", is_flag=True, default=False, help="若無觸發買訊，是否仍發送每日收盤狀態總結（適合收盤後使用）")
@click.option("--intraday/--no-intraday", default=True, help="是否優先抓取盤中即時報價（預設開啟）")
@click.pass_context
def cmd_watch_entry(ctx, stock, notify, summary, intraday):
    """即時監控標的空手進場點雷達（支援盤中即時報價與回踩/突破觸碰偵測）。"""
    from datetime import date, timedelta
    import requests
    from stock_backtester.data.data_manager import DataManager
    from stock_backtester.notifiers.telegram_notifier import TelegramNotifier

    dm = DataManager()
    end_d = date.today()
    start_d = end_d - timedelta(days=250)

    with console.status(f"[cyan]讀取 {stock} 最新數據並計算進場雷達...[/cyan]"):
        df = dm.get_ohlcv(stock, start_d, end_d)

    if df.empty:
        console.print(f"[red]❌ 無法取得 {stock} 的行情數據[/red]")
        raise click.Abort()

    close = df["close"]
    high = df["high"]
    low_s = df["low"]
    open_p = df["open"]

    latest_c = float(close.iloc[-1])
    latest_o = float(open_p.iloc[-1])
    latest_h = float(high.iloc[-1])
    latest_l = float(low_s.iloc[-1])
    latest_dt = df.index[-1].strftime("%Y-%m-%d")

    # 嘗試抓取 TWSE 即時報價（若有開盤或最新撮合）
    is_realtime = False
    if intraday:
        try:
            twse_url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock}.tw&json=1&delay=0"
            r_rt = requests.get(twse_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
            items = r_rt.json().get("msgArray", [])
            if items:
                it = items[0]
                z = it.get("z")
                if z == "-" or not z:
                    bids = it.get("b", "_").split("_")
                    z = bids[0] if bids and bids[0] != "" else it.get("y")
                if z and z != "-":
                    latest_c = float(z)
                    is_realtime = True
                if it.get("h") and it.get("h") != "-":
                    latest_h = max(latest_h, float(it.get("h")))
                if it.get("l") and it.get("l") != "-":
                    latest_l = min(latest_l, float(it.get("l")))
                if it.get("o") and it.get("o") != "-":
                    latest_o = float(it.get("o"))
        except Exception:
            pass

    ma60 = float(close.rolling(60, min_periods=1).mean().iloc[-1])
    bias = (latest_c - ma60) / ma60 * 100.0

    roll_20_h = float(high.rolling(20, min_periods=1).max().shift(1).iloc[-1]) if len(df) >= 20 else float(high.max())
    capitulation_p = ma60 * 0.94

    dist_breakout = roll_20_h - latest_c
    pct_breakout = (dist_breakout / latest_c) * 100.0

    pullback_min_p = ma60 * 0.98
    pullback_max_p = ma60 * 1.01
    # 盤中觸碰判定
    is_pullback = (-2.0 <= bias <= 1.0) and (latest_c > latest_o)
    is_touch_pullback = (latest_l <= pullback_max_p and latest_c >= pullback_min_p * 0.98)

    tier2_max_p = roll_20_h * 0.92
    tier2_min_p = roll_20_h * 0.90
    dist_tier2 = latest_c - tier2_max_p
    pct_tier2 = (dist_tier2 / latest_c) * 100.0
    is_tier2 = (tier2_min_p <= latest_c <= tier2_max_p) and (latest_c > latest_o)
    is_touch_tier2 = (latest_l <= tier2_max_p and latest_c >= tier2_min_p * 0.98)

    dist_pullback = latest_c - pullback_max_p
    pct_pullback = (dist_pullback / latest_c) * 100.0

    is_breakout = (latest_c > roll_20_h and bias > 0)
    is_touch_breakout = (latest_h >= roll_20_h)
    is_panic = (bias <= -6.0 and latest_c > latest_o)
    is_touch_panic = (latest_l <= capitulation_p)

    table = Table(title=f"🎯 {stock} 空手進場點雷達監控 (截至 {latest_dt})", show_header=True, header_style="bold cyan")
    table.add_column("監控維度", style="bold")
    table.add_column("關鍵數值 / 門檻", justify="right")
    table.add_column("目前狀態與距離", style="bold")

    table.add_row("最新收盤價", f"${latest_c:.2f}", "基準現價")
    table.add_row("60 日季線 (MA60)", f"${ma60:.2f}", f"乖離率 {bias:+.2f}%")
    table.add_row(
        "🚀 右側強勢突破點",
        f"${roll_20_h:.2f}",
        f"[green]🚨 已滿足突破進場！[/green]" if is_breakout else f"[yellow]距離僅差 {dist_breakout:+.2f} 元 (+{pct_breakout:.2f}%)[/yellow]"
    )
    table.add_row(
        "🎯 第一梯隊：季線回踩區",
        f"${pullback_min_p:.2f} ~ ${pullback_max_p:.2f}",
        f"[green]🚨 已在回踩區且收紅！[/green]" if is_pullback else (
            f"[cyan]拉回 {pct_pullback:.2f}% (約差 {dist_pullback:.2f} 元) 進抄底區[/cyan]" if latest_c > pullback_max_p else "[yellow]低於回踩區[/yellow]"
        )
    )
    table.add_row(
        "🌟 第二梯隊：波段黃金區",
        f"${tier2_min_p:.2f} ~ ${tier2_max_p:.2f}",
        f"[green]🚨 已在黃金區且收紅！[/green]" if is_tier2 else (
            f"[magenta]距前高拉回 -8%~-10% (差 {dist_tier2:.2f} 元)[/magenta]" if latest_c > tier2_max_p else "[yellow]低於黃金區[/yellow]"
        )
    )
    table.add_row(
        "🛡️ 第三梯隊：極度恐慌點",
        f"<= ${capitulation_p:.2f}",
        f"[green]🚨 已滿足恐慌抄底！[/green]" if is_panic else f"[dim]需拉回 {((latest_c - capitulation_p)/latest_c)*100:.2f}%[/dim]"
    )

    console.print(table)

    signal_triggered = is_breakout or is_pullback or is_tier2 or is_panic or is_touch_breakout or is_touch_pullback or is_touch_tier2 or is_touch_panic
    if signal_triggered:
        reasons = []
        if is_breakout:
            reasons.append("🚀 突破 20 日高點")
        elif is_touch_breakout:
            reasons.append(f"⚡ 盤中觸碰突破價 (最高 {latest_h:.2f} 元)")

        if is_pullback:
            reasons.append("🎯 第一梯隊：季線回踩守穩收紅")
        elif is_touch_pullback:
            reasons.append(f"⚡ 盤中踩入第一梯隊抄底區 (最低 {latest_l:.2f} 元)")

        if is_tier2:
            reasons.append("🌟 第二梯隊：波段黃金拉回區收紅")
        elif is_touch_tier2:
            reasons.append(f"⚡ 盤中踩入第二梯隊黃金區 (最低 {latest_l:.2f} 元)")

        if is_panic:
            reasons.append("🛡️ 第三梯隊：季線負乖離超跌落底")
        elif is_touch_panic:
            reasons.append(f"⚡ 盤中觸碰極度恐慌底 (最低 {latest_l:.2f} 元)")

        reason_str = " & ".join(reasons)
        quote_url = f"https://tw.stock.yahoo.com/quote/{stock}.TW"

        action_msg = (
            f"🚨 <b>【{stock} 進場雷達快訊】</b>\n\n"
            f"• 訊號類型：<b>{reason_str}</b>\n"
            f"• 最新成交價：<a href='{quote_url}'><b>{latest_c:.2f} 元</b></a>\n"
            f"• 盤中高低：最高 {latest_h:.2f} 元 / 最低 {latest_l:.2f} 元\n"
            f"• 季線 MA60：{ma60:.2f} 元 (乖離 {bias:+.2f}%)\n"
            f"• 監控時間：{latest_dt}\n\n"
            f"💡 <b>操作建議</b>：請留意盤面守穩狀況，依紀律進場並設好 -8% 停損防守。"
        )
        console.print(f"\n[bold green]🚨 買進訊號已觸發：{reason_str}！[/bold green]")
        if notify:
            token, chat_id = _load_env_to_os()
            if token and chat_id and token != "your_bot_token_here":
                notifier = TelegramNotifier(token=token, chat_id=chat_id)
                notifier.send(action_msg)
                console.print("[green]✅ 已發送 Telegram 即時通知！[/green]")
            else:
                console.print("[yellow]⚠️ 未設定 Telegram憑證，請在 .env 填入 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID。[/yellow]")
    else:
        console.print(f"\n[cyan]⏳ 目前持續追蹤中（未達進場門檻）：[/cyan]")
        console.print(f"  • 距【右側突破進場價 ${roll_20_h:.2f}】僅差 [bold green]+{pct_breakout:.2f}%[/bold green]")
        console.print(f"  • 距【第一梯隊季線回踩區 ${pullback_min_p:.2f} ~ ${pullback_max_p:.2f}】僅差 [bold cyan]-{pct_pullback:.2f}%[/bold cyan]")
        if notify and summary:
            token, chat_id = _load_env_to_os()
            if token and chat_id and token != "your_bot_token_here":
                notifier = TelegramNotifier(token=token, chat_id=chat_id)
                quote_url = f"https://tw.stock.yahoo.com/quote/{stock}.TW"
                status_msg = (
                    f"🏁 <b>【{stock} 今日收盤雷達總結】</b>\n\n"
                    f"📊 <b>收盤行情與雷達價位 ({latest_dt})：</b>\n"
                    f"• 今日收盤價：<a href='{quote_url}'><b>{latest_c:.2f} 元</b></a> (季線 {bias:+.2f}%)\n"
                    f"• 盤中高低：最高 {latest_h:.2f} 元 / 最低 {latest_l:.2f} 元\n"
                    f"• 🚀 <b>右側強勢突破點</b>：<a href='{quote_url}'><b>{roll_20_h:.2f} 元</b></a> (差 +{pct_breakout:.2f}%)\n"
                    f"• 🎯 <b>第一梯隊(季線回踩)</b>：<a href='{quote_url}'><b>{pullback_min_p:.2f} ~ {pullback_max_p:.2f} 元</b></a> (差 {dist_pullback:.2f} 元)\n"
                    f"• 🌟 <b>第二梯隊(波段黃金)</b>：<a href='{quote_url}'><b>{tier2_min_p:.2f} ~ {tier2_max_p:.2f} 元</b></a>\n"
                    f"• 🛡️ <b>第三梯隊(恐慌超跌)</b>：≤ <a href='{quote_url}'><b>{capitulation_p:.2f} 元</b></a> (季線負乖離 ≤ -6%)\n\n"
                    f"☕ <b>總結狀態</b>：今日未達進場門檻，維持空手觀望。明日開盤將繼續實時盯盤！"
                )
                if notifier.send(status_msg):
                    console.print("[green]✅ 已發送 Telegram 今日收盤總結推播！[/green]")
            else:
                console.print("[dim]提示：加上 Telegram 通知可在 .env 設定憑證。[/dim]")
        elif notify and not summary:
            console.print("[dim]💡 盤中巡檢模式：未觸發進場訊號，保持靜默不打擾。[/dim]")


@main.command("watch-live")
@click.option("--stocks", "-s", default="0050,0052", help="股票代號清單（逗號分隔，預設：0050,0052）")
@click.option("--notify/--no-notify", default=True, help="是否發送 Telegram 即時急報（預設開啟）")
@click.option("--summary/--no-summary", default=True, help="收盤時是否發送今日總結（預設開啟）")
@click.option("--interval", default=60, type=int, help="盤中輪詢間隔秒數（預設 60 秒）")
@click.option("--max-alerts", default=5, type=int, help="單檔標的每日盤中最大推播次數（預設 5 次，滿 5 次自動靜默）")
@click.option("--cooldown", default=180, type=int, help="相同標的兩次推播間隔冷卻秒數（預設 180 秒，防止短時間密集洗版）")
@click.option("--daemon/--once", default=False, help="模式：--daemon 常駐即時監控直到收盤；--once 僅執行單次檢測")
@click.option("--test", is_flag=True, default=False, help="立即發送一則測試通知以驗證連線")
@click.pass_context
def cmd_watch_live(ctx, stocks, notify, summary, interval, max_alerts, cooldown, daemon, test):
    """【盤中實時進場雷達】毫秒級即時撮合監控，碰觸策略門檻立即發送 Telegram 急報！"""
    from stock_backtester.scanner.live_radar import LiveEntryRadar
    from stock_backtester.notifiers.telegram_notifier import TelegramNotifier

    stock_list = [s.strip() for s in stocks.split(",") if s.strip()]
    console.print(f"[bold cyan]🎯 盤中實時進場雷達啟動[/bold cyan] ── 監控標的: {', '.join(stock_list)} | 輪詢頻率: {interval}秒 | 當日上限: {max_alerts}次 (冷卻 {cooldown}s)")

    notifier = None
    if notify or test:
        token, chat_id = _load_env_to_os()
        if token and chat_id and token != "your_bot_token_here":
            notifier = TelegramNotifier(token=token, chat_id=chat_id)
            if test:
                console.print("[cyan]發送 Telegram 測試急報...[/cyan]")
                notifier.send("🧪 <b>【盤中實時進場雷達測試】</b>\n\nTelegram 通道連線正常！盤中碰價時將在此 30 秒內極速推播。")
                console.print("[green]✅ 測試訊息已發送至 Telegram！[/green]")
        else:
            console.print("[yellow]⚠️ 未設定 Telegram 憑證，將僅在終端輸出，不發送推播。[/yellow]")

    radar = LiveEntryRadar(
        stocks=stock_list,
        notifier=notifier,
        poll_interval=interval,
        max_alerts_per_stock=max_alerts,
        cooldown_seconds=cooldown,
    )

    with console.status("[cyan]計算歷史門檻與抓取撮合行情...[/cyan]"):
        targets = radar.load_targets()
        quotes = radar.fetch_quotes()

    # 輸出表格
    table = Table(title="🎯 盤中實時進場雷達監控看板", show_header=True, header_style="bold cyan")
    table.add_column("代號", style="bold")
    table.add_column("標的名稱")
    table.add_column("現價 (撮合時間)", justify="right")
    table.add_column("盤中高 / 低", justify="center")
    table.add_column("🚀 20日突破價", justify="right")
    table.add_column("🎯 季線回踩區", justify="center")
    table.add_column("🛑 季線防守", justify="right")
    table.add_column("即時觸碰狀態", style="bold")
    table.add_column("今日推播次數", justify="center")

    for s in stock_list:
        t = targets.get(s)
        q = quotes.get(s)
        if not t or not q:
            continue

        is_bo = (q.high_price >= t.roll_20_h or q.current_price >= t.roll_20_h)
        is_pb = (q.low_price <= t.pullback_max_p and q.current_price >= t.pullback_min_p * 0.98)
        is_sl = (q.current_price < t.ma60 * 0.98)

        status_str = "[dim]持續追蹤中[/dim]"
        if is_sl:
            status_str = "[red]🛑 跌破季線防守！[/red]"
        elif is_bo:
            status_str = "[green]🚨 盤中已突破！[/green]"
        elif is_pb:
            status_str = "[cyan]🎯 踩入季線回踩區[/cyan]"

        cnt = radar.alert_counts.get(s, 0)
        cnt_str = f"[bold yellow]{cnt}/{max_alerts}[/bold yellow]" if cnt > 0 else f"{cnt}/{max_alerts}"
        if cnt >= max_alerts:
            cnt_str = f"[red]已滿 {max_alerts} 次 (靜默)[/red]"

        sl_price = round(t.ma60 * 0.98, 2)

        table.add_row(
            s,
            q.name,
            f"${q.current_price:.2f} ({q.trade_time})",
            f"${q.high_price:.2f} / ${q.low_price:.2f}",
            f"${t.roll_20_h:.2f}",
            f"${t.pullback_min_p:.2f} ~ ${t.pullback_max_p:.2f}",
            f"${sl_price:.2f}",
            status_str,
            cnt_str,
        )

    console.print(table)

    # ── 預覽目前狀態（僅顯示，不發送 Telegram、不消耗推播額度）──
    # 注意：send_telegram=False 確保此次預覽不會佔用 alerted_events，
    # 避免 daemon 模式啟動後因事件已被標記而永遠無法再觸發盤中訊號。
    signals = radar.check_and_alert(quotes, send_telegram=False)
    if signals:
        for sig in signals:
            console.print(f"[bold green]🚨 目前狀態已達觸發條件: {sig['stock']} {sig['title']}（Daemon 模式下將正式發送推播）[/bold green]")
    else:
        console.print("[dim]目前無新觸發訊號，維持觀望。[/dim]")

    if daemon:
        # 設定 INFO 級別 logging 讓 daemon 過程中 log 可見
        logging.getLogger("stock_backtester").setLevel(logging.INFO)
        if not any(
            isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers
        ):
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )

        console.print(f"[bold green]⚡ 進入常駐巡檢守護模式（每 {interval} 秒檢查一次，持續至 13:35 收盤）...[/bold green]")
        console.print("[dim]提示：按 Ctrl+C 可隨時中止常駐監控。[/dim]")
        try:
            radar.run_daemon()
        except KeyboardInterrupt:
            console.print("\n[yellow]已手動停止盤中雷達守護行程。[/yellow]")


if __name__ == "__main__":
    main()

