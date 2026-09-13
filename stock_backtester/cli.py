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
@click.pass_context
def cmd_watch_entry(ctx, stock, notify):
    """即時監控標的空手進場點雷達（右側突破 $110.75 / 左側抄底 $98.55）。"""
    from datetime import date, timedelta
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
    open_p = df["open"]

    latest_c = float(close.iloc[-1])
    latest_o = float(open_p.iloc[-1])
    latest_dt = df.index[-1].strftime("%Y-%m-%d")

    ma60 = float(close.rolling(60, min_periods=1).mean().iloc[-1])
    bias = (latest_c - ma60) / ma60 * 100.0

    roll_20_h = float(high.rolling(20, min_periods=1).max().shift(1).iloc[-1]) if len(df) >= 20 else float(high.max())
    capitulation_p = ma60 * 0.94

    dist_breakout = roll_20_h - latest_c
    pct_breakout = (dist_breakout / latest_c) * 100.0

    pullback_min_p = ma60 * 0.98
    pullback_max_p = ma60 * 1.01
    is_pullback = (-2.0 <= bias <= 1.0) and (latest_c > latest_o)

    dist_pullback = latest_c - pullback_max_p
    pct_pullback = (dist_pullback / latest_c) * 100.0

    is_breakout = (latest_c > roll_20_h and bias > 0)
    is_panic = (bias <= -6.0 and latest_c > latest_o)

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
        "🎯 季線回踩抄底區",
        f"${pullback_min_p:.2f} ~ ${pullback_max_p:.2f}",
        f"[green]🚨 已在抄底區且收紅！[/green]" if is_pullback else (
            f"[cyan]拉回 {pct_pullback:.2f}% (約差 {dist_pullback:.2f} 元) 進抄底區[/cyan]" if latest_c > pullback_max_p else "[yellow]低於回踩區[/yellow]"
        )
    )
    table.add_row(
        "🛡️ 極度恐慌抄底點",
        f"<= ${capitulation_p:.2f}",
        f"[green]🚨 已滿足恐慌抄底！[/green]" if is_panic else f"[dim]需拉回 {((latest_c - capitulation_p)/latest_c)*100:.2f}%[/dim]"
    )

    console.print(table)

    if is_breakout or is_panic:
        action_msg = f"🚀 <b>{stock} 出現買進訊號！</b>\n最新價: ${latest_c:.2f}\n原因: " + ("突破 20 日高點" if is_breakout else "季線超跌落底翻紅")
        console.print(f"\n[bold green]🚨 買進訊號已觸發！[/bold green]")
        if notify:
            token, chat_id = _load_env_to_os()
            if token and chat_id and token != "your_bot_token_here":
                notifier = TelegramNotifier(token=token, chat_id=chat_id)
                notifier.send(action_msg)
                console.print("[green]✅ 已發送 Telegram 通知！[/green]")
    else:
        console.print(f"\n[cyan]⏳ 目前持續追蹤中：距離突破進場價 ${roll_20_h:.2f} 僅差 +{pct_breakout:.2f}%。[/cyan]")


if __name__ == "__main__":
    main()
