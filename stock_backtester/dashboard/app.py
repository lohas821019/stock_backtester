"""
Stock Backtester Dashboard - Quant Terminal Pro

Streamlit 高質感量化回測終端
啟動方式：python3 run_dashboard.py
"""

import sys
from pathlib import Path
from datetime import date, timedelta, datetime

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np

# ── 路徑設定 ──────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── 預載入本地模組（確保 Streamlit Cloud 路徑正確）────────────────────
# 雙重保險：即使 import 失敗也有完整的美股清單，不會讓 selectbox index 越界
_US_STOCKS_FALLBACK = [
    {"symbol": "NVDA",  "name": "輝達 (NVIDIA)"},
    {"symbol": "AAPL",  "name": "蘋果 (Apple)"},
    {"symbol": "MSFT",  "name": "微軟 (Microsoft)"},
    {"symbol": "GOOGL", "name": "Alphabet (Google)"},
    {"symbol": "AMZN",  "name": "亞馬遜 (Amazon)"},
    {"symbol": "TSLA",  "name": "特斯拉 (Tesla)"},
    {"symbol": "META",  "name": "Meta (Facebook)"},
    {"symbol": "TSM",   "name": "台積電 ADR"},
    {"symbol": "AVGO",  "name": "博通 (Broadcom)"},
    {"symbol": "AMD",   "name": "超微 (AMD)"},
    {"symbol": "QQQ",   "name": "那斯達克100 ETF (Invesco QQQ)"},
    {"symbol": "SPY",   "name": "標普500 ETF (SPDR S&P 500)"},
    {"symbol": "SOXX",  "name": "費城半導體 ETF (iShares)"},
    {"symbol": "SMH",   "name": "VanEck 半導體 ETF"},
    {"symbol": "PLTR",  "name": "Palantir"},
    {"symbol": "COIN",  "name": "Coinbase"},
    {"symbol": "ARM",   "name": "Arm Holdings"},
    {"symbol": "MU",    "name": "美光科技 (Micron)"},
    {"symbol": "ASML",  "name": "艾司摩爾 (ASML)"},
    {"symbol": "INTC",  "name": "英特爾 (Intel)"},
]

try:
    from stock_backtester.data.constituents import (
        US_POPULAR_STOCKS,
        get_us_popular_options,
    )
    _us_import_ok = True
except Exception:
    US_POPULAR_STOCKS = _US_STOCKS_FALLBACK

    def get_us_popular_options() -> list[str]:  # type: ignore[misc]
        return [f"{s['symbol']} {s['name']}" for s in _US_STOCKS_FALLBACK]

    _us_import_ok = False


# ── 頁面設定（必須是第一個 st 呼叫）─────────────────────────────────
st.set_page_config(
    page_title="Stock Backtester Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 注入極致高質感 Dark Quant Terminal CSS ────────────────────────────
st.markdown("""
<style>
/* 1. 純淨高級消光深色背景 (Clean Matte Dark Slate) */
html, body, [data-testid="stAppViewContainer"], .main, .stApp {
    background-color: #0B0F19 !important;
    background-image: none !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #E2E8F0;
}

/* 隱藏輔助用零高度 iframe (如 K 線價格軸動態縮放監聽器) */
iframe[height="0"], div[data-testid="stIFrame"]:has(iframe[height="0"]) {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
}

/* 消除頂部 Header 奇怪的白色/半透明覆蓋 */
[data-testid="stHeader"] {
    background-color: #0B0F19 !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

/* 側邊欄基礎造型與流暢過渡動畫 */
section[data-testid="stSidebar"] {
    background-color: #0E131F !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    transition: min-width 0.3s cubic-bezier(0.4, 0, 0.2, 1), 
                max-width 0.3s cubic-bezier(0.4, 0, 0.2, 1), 
                transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                width 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* 側邊欄展開狀態：維持舒適的寬度，確保所有控制元件不遮擋 */
section[data-testid="stSidebar"]:not([aria-expanded="false"]) {
    min-width: 340px !important;
    max-width: 380px !important;
    width: 360px !important;
}

section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding-bottom: 5rem !important;
}

/* 側邊欄收合（縮小）狀態：徹底歸零，寬度 100% 釋放給主畫面 */
section[data-testid="stSidebar"][aria-expanded="false"] {
    min-width: 0px !important;
    max-width: 0px !important;
    width: 0px !important;
    padding: 0px !important;
    margin: 0px !important;
    border: none !important;
    overflow: hidden !important;
}

section[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.5rem;
    padding-left: 1.2rem;
    padding-right: 1.2rem;
}

/* 側邊欄收合與展開按鈕美化 */
[data-testid="stSidebarCollapseButton"] {
    color: #94A3B8 !important;
    transition: color 0.2s ease !important;
}
[data-testid="stSidebarCollapseButton"]:hover {
    color: #38BDF8 !important;
}

[data-testid="stExpandSidebarButton"] {
    color: #38BDF8 !important;
    background-color: #131B2A !important;
    border: 1px solid rgba(56, 189, 248, 0.3) !important;
    border-radius: 6px !important;
    margin: 6px 10px !important;
    transition: all 0.2s ease !important;
}
[data-testid="stExpandSidebarButton"]:hover {
    background-color: #0284C7 !important;
    color: #FFFFFF !important;
    border-color: #38BDF8 !important;
}

/* 主畫面容器自適應流動排版（側邊欄收合時自動無縫全螢幕展開） */
[data-testid="stMain"], section.main {
    flex: 1 1 0% !important;
    width: 100% !important;
    min-width: 0 !important;
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.main .block-container {
    max-width: 100% !important;
    width: 100% !important;
    padding-top: 1.6rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: clamp(1.2rem, 2.5vw, 3rem) !important;
    padding-right: clamp(1.2rem, 2.5vw, 3rem) !important;
    transition: padding 0.3s ease !important;
}

/* 圖表與卡片容器 100% 響應式填滿 */
[data-testid="stPlotlyChart"], .js-plotly-plot, .plot-container {
    width: 100% !important;
}

/* 主頁標題 */
.hero-title {
    font-size: 1.75rem;
    font-weight: 750;
    color: #F8FAFC;
    letter-spacing: -0.02em;
    margin-bottom: 4px;
}
.hero-sub {
    color: #64748B;
    font-size: 0.88rem;
    margin-bottom: 20px;
}

/* 頂部 KPI 卡片：純淨平整消光卡片 */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.kpi-card {
    background-color: #131B2A;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(56, 189, 248, 0.4);
}
.kpi-top-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: #334155;
}
.kpi-top-pos { background: #10B981; }
.kpi-top-neg { background: #EF4444; }
.kpi-top-cyan{ background: #0284C7; }

.kpi-label {
    color: #94A3B8;
    font-size: 0.74rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}
.kpi-value {
    color: #F8FAFC;
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.01em;
}
.kpi-sub {
    font-size: 0.70rem;
    color: #64748B;
    margin-top: 2px;
}
.val-pos { color: #34D399 !important; }
.val-neg { color: #F87171 !important; }

/* Tabs 分頁設計 */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background-color: #131B2A;
    padding: 5px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
.stTabs [data-baseweb="tab"] {
    padding: 7px 16px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.86rem;
    color: #94A3B8;
    background-color: transparent;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background-color: #1E293B !important;
    color: #38BDF8 !important;
}

/* 按鈕美化 */
div.stButton > button:first-child {
    background: #0284C7;
    color: #FFFFFF;
    font-weight: 600;
    border-radius: 7px;
    border: 1px solid rgba(56, 189, 248, 0.3);
    transition: background 0.15s ease;
}
div.stButton > button:first-child:hover {
    background: #0369A1;
    border-color: #38BDF8;
}

/* 資金說明 Tooltip 小圖示 */
.info-hint-container {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-top: 6px;
    margin-bottom: 14px;
}
.info-hint-pill {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #131B2A;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.83rem;
    color: #CBD5E1;
    cursor: pointer;
    transition: all 0.2s ease;
}
.info-hint-pill:hover {
    border-color: #38BDF8;
    background: rgba(56, 189, 248, 0.12);
    color: #FFFFFF;
}
.info-hint-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 17px;
    height: 17px;
    border-radius: 50%;
    background: rgba(56, 189, 248, 0.25);
    color: #38BDF8;
    font-size: 11px;
    font-weight: 700;
}
.info-hint-tooltip {
    visibility: hidden;
    opacity: 0;
    width: 300px;
    background-color: #0F172A;
    color: #E2E8F0;
    text-align: left;
    border: 1px solid #38BDF8;
    border-radius: 8px;
    padding: 10px 14px;
    position: absolute;
    z-index: 9999;
    bottom: 130%;
    left: 50%;
    transform: translateX(-50%);
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.6);
    font-size: 0.78rem;
    line-height: 1.5;
    transition: opacity 0.2s ease, visibility 0.2s ease;
    pointer-events: none;
}
.info-hint-tooltip::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: #38BDF8 transparent transparent transparent;
}
.info-hint-pill:hover .info-hint-tooltip {
    visibility: visible;
    opacity: 1;
}

/* 全局說明文字精簡化 (精簡字級、降低干擾) */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.75rem !important;
    color: #64748B !important;
    line-height: 1.35 !important;
}
</style>
""", unsafe_allow_html=True)



# ════════════════════════════════════════════════════════════════════════
# 快取與回測核心函式
# ════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def _load_data(symbol: str, start: date, end: date, market: str, force_refresh: bool = False, cache_version: str = "v2") -> tuple[pd.DataFrame, bool]:
    from stock_backtester.data.data_manager import DataManager
    dm = DataManager()
    df = dm.get_ohlcv(symbol, start, end, market=market, force_refresh=force_refresh)
    if not df.empty:
        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        df = df[(df["open"] > 0) & (df["close"] > 0)]
    is_cache = getattr(dm, "last_cache_hit", False)
    return df, is_cache


def _run_backtest(df: pd.DataFrame, strategy_name: str, params: dict, capital: float, symbol: str):
    from stock_backtester.strategies import get_strategy
    from stock_backtester.engine.backtest_engine import BacktestEngine

    StratClass = get_strategy(strategy_name)
    strategy = StratClass(**params)
    engine = BacktestEngine(initial_capital=capital)
    return engine.run(df, strategy, symbol=symbol)


def _get_metrics(result) -> dict:
    from stock_backtester.analysis.performance import PerformanceAnalyzer
    return PerformanceAnalyzer().analyze(result)


def _render_kpi_card(label: str, value: str, sub: str = "", status: str = "neutral") -> str:
    color_cls = ""
    top_cls = "kpi-top-cyan"
    if status == "pos":
        color_cls = "val-pos"
        top_cls = "kpi-top-pos"
    elif status == "neg":
        color_cls = "val-neg"
        top_cls = "kpi-top-neg"

    return f"""
    <div class="kpi-card">
        <div class="kpi-top-bar {top_cls}"></div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {color_cls}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


# ════════════════════════════════════════════════════════════════════════
# 側邊欄設計 (Sidebar Controls)
# ════════════════════════════════════════════════════════════════════════

with st.sidebar:
    page = st.radio(
        "導航功能",
        ["🔬 回測分析實驗室", "🇺🇸 美股量化監控與進場雷達", "📋 策略庫總覽"],
        label_visibility="collapsed",
    )
    st.markdown("---")


# ════════════════════════════════════════════════════════════════════════
# 📋 策略庫總覽 (Strategy Library View)
# ════════════════════════════════════════════════════════════════════════

if page == "📋 策略庫總覽":
    st.markdown('<div class="hero-title">📋 策略庫總覽</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">已掛載的量化策略外掛。系統支援熱插拔，新增 .py 策略檔案後重新整理即可即時載入。</div>', unsafe_allow_html=True)

    from stock_backtester.strategies import list_strategies, get_strategy
    strategies = list_strategies()

    cols = st.columns(2)
    icons = {
        "weekly_kd_passivation": ("🛡️", "週 KD 鈍化守護", "#10B981"),
        "monthly_kd_passivation": ("👑", "月 KD 鈍化大波段", "#F59E0B"),
        "monthly_rsi": ("🌌", "月 RSI 鈍化大波段", "#6366F1"),
        "weekly_rsi": ("🏄", "週 RSI 鈍化波段守護", "#06B6D4"),
        "weekly_kd_rsi": ("⚡", "多時間週期共振", "#38BDF8"),
        "weekly_kd": ("⏳", "週線 KD 超買超賣", "#818CF8"),
        "daily_kd": ("📊", "日線 KD 超買超賣", "#F43F5E"),
        "daily_rsi": ("🌊", "日線 RSI 超買超賣", "#34D399"),
        "ma_cross": ("📈", "雙均線趨勢追蹤", "#FBBF24"),
        "bollinger_band": ("🎯", "布林通道波動突破", "#A855F7"),
    }

    for i, s in enumerate(strategies):
        s_name = s["name"]
        icon, tag, color = icons.get(s_name, ("💡", "量化模型", "#94A3B8"))

        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
                    f"<span style='font-size:1.2rem; font-weight:700;'>{icon} <code>{s_name}</code></span>"
                    f"<span style='background:{color}22; color:{color}; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600;'>{tag}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.markdown(f"**說明**：{s['description']}")
                st.caption(f"綁定類別：`{s['class']}`")

                # 提取參數簽名
                try:
                    cls = get_strategy(s_name)
                    import inspect
                    sig = inspect.signature(cls.__init__)
                    params = {
                        k: v.default
                        for k, v in sig.parameters.items()
                        if k != "self" and v.default is not inspect.Parameter.empty
                    }
                    if params:
                        st.markdown("**預設超參數**：")
                        p_tags = " ".join([f"<code style='color:#38BDF8;'>{k}={v}</code>" for k, v in params.items()])
                        st.markdown(p_tags, unsafe_allow_html=True)
                except Exception:
                    pass

    st.markdown("---")
    st.markdown("""
    #### 🛠️ 如何撰寫新策略？
    只需在 `stock_backtester/strategies/` 目錄建立新檔案，繼承 `BaseStrategy` 並實作 `generate_signals`：
    ```python
    from stock_backtester.strategies.base_strategy import BaseStrategy
    import pandas as pd

    class MyCustomStrategy(BaseStrategy):
        name = "my_strategy"
        description = "自訂中長線量化策略"

        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            signal = pd.Series(0, index=data.index, dtype=int)
            # signal[...] = 1   # 買進
            # signal[...] = -1  # 賣出
            return signal
    ```
    """)


# ════════════════════════════════════════════════════════════════════════
# 🔬 回測分析實驗室 (Backtest Lab View)
# ════════════════════════════════════════════════════════════════════════

elif page == "🔬 回測分析實驗室":

    with st.sidebar:
        from stock_backtester.strategies import list_strategies, get_strategy
        import inspect

        # ── 1. 選擇策略 ────────────────────────────────────────────────
        st.markdown("#### 🧠 **1. 選擇策略**")

        strategy_list = list_strategies()
        category_order = [
            "parabolic_climax_alpha",
            "weekly_kd_passivation",
            "monthly_kd_passivation",
            "monthly_rsi",
            "weekly_rsi",
            "weekly_kd_rsi",
            "weekly_kd",
            "daily_kd",
            "daily_rsi",
            "ma_cross",
            "bollinger_band",
        ]
        strategy_names = sorted(
            [s["name"] for s in strategy_list],
            key=lambda x: category_order.index(x) if x in category_order else 999
        )

        default_strat_idx = strategy_names.index("parabolic_climax_alpha") if "parabolic_climax_alpha" in strategy_names else 0

        selected_strategy = st.selectbox(
            "回測策略",
            strategy_names,
            index=default_strat_idx,
            label_visibility="collapsed",
        )

        strat_info = next(s for s in strategy_list if s["name"] == selected_strategy)
        st.caption(f"💡 {strat_info['description']}")

        st.markdown("---")

        # ── 2. 選擇股票 ────────────────────────────────────────────────
        st.markdown("#### 📌 **2. 選擇股票**")

        from stock_backtester.data.constituents import TAIWAN_50_STOCKS

        t50_options = ["(自訂輸入)"] + [f"{item['symbol']} {item['name']}" for item in TAIWAN_50_STOCKS]
        selected_t50 = st.selectbox(
            "快捷標的",
            t50_options,
            index=1,  # 預設 0050 ETF
            help="選擇 0050 或台股市值前 50 大權值股",
            label_visibility="collapsed",
        )

        if selected_t50 != "(自訂輸入)":
            symbol = selected_t50.split()[0]
            st.text_input(
                "股票代號 (Symbol)",
                value=symbol,
                disabled=True,
                help="已由上方快捷選單連動。若要手動輸入美股或其他代號，請將上方改為「(自訂輸入)」",
            )
        else:
            symbol = st.text_input(
                "股票代號 (Symbol)",
                value="0050",
                help="支援台股 (如 0050, 2330, 2454) 或美股 (如 AAPL, NVDA, TSM)",
            ).strip().upper()

        st.markdown("---")

        # ── 3. 投入金額 ────────────────────────────────────────────────
        st.markdown("#### 💰 **3. 投入金額 (TWD)**")
        capital = st.number_input(
            "初始資金 (TWD)",
            value=1_000_000,
            step=100_000,
            min_value=100_000,
            label_visibility="collapsed",
        )

        st.markdown("---")

        # ── 4. 額外選項 toggle 拓展調整 ─────────────────────────────────
        show_advanced = st.toggle("⚙️ 額外選項拓展調整", value=False, help="開啟後可自訂回測日期區間、策略細部超參數、市場類型與快取重整")

        # 預設值與 Session State 狀態保存（收合時不遺失調整過的數值）
        today_d = date.today()
        if "custom_date_start" not in st.session_state:
            st.session_state["custom_date_start"] = date(2026, 1, 1)
        # 每次都強制更新結束日期為今天，避免 session 殘留舊日期導致資料停在過去
        st.session_state["custom_date_end"] = today_d
        if "custom_market" not in st.session_state:
            st.session_state.custom_market = "auto"
        if "custom_force_refresh" not in st.session_state:
            st.session_state.custom_force_refresh = False

        def _on_period_preset_change():
            choice = st.session_state.get("sidebar_period_preset_radio", "")
            t_now = date.today()
            if "2026 YTD" in choice:
                st.session_state["custom_date_start"] = date(2026, 1, 1)
                st.session_state["custom_date_end"] = t_now
            elif "近 1 年" in choice:
                st.session_state["custom_date_start"] = date(t_now.year - 1, t_now.month, t_now.day)
                st.session_state["custom_date_end"] = t_now
            elif "近 3 年" in choice:
                st.session_state["custom_date_start"] = date(t_now.year - 3, t_now.month, t_now.day)
                st.session_state["custom_date_end"] = t_now
            elif "近 5 年" in choice:
                st.session_state["custom_date_start"] = date(t_now.year - 5, t_now.month, t_now.day)
                st.session_state["custom_date_end"] = t_now

        # 提取策略超參數預設值
        cls = get_strategy(selected_strategy)
        sig = inspect.signature(cls.__init__)
        strategy_params = {}
        for k, v in sig.parameters.items():
            if k == "self" or v.default is inspect.Parameter.empty:
                continue
            strategy_params[k] = v.default

        if show_advanced:
            with st.container(border=True):
                st.markdown("##### 📅 **回測日期區間**")
                period_presets = [
                    "⚡ 2026 年初至今 (2026 YTD)",
                    "📅 近 1 年 (1 Year)",
                    "📈 近 3 年 (3 Years)",
                    "🏆 近 5 年 (5 Years)",
                    "✏️ 自訂日期區間",
                ]

                # 依當前 custom_date_start 自動對應預設選項
                cur_start = st.session_state.get("custom_date_start", date(2026, 1, 1))
                if cur_start == date(2026, 1, 1):
                    default_p_idx = 0
                elif cur_start == date(today_d.year - 1, today_d.month, today_d.day):
                    default_p_idx = 1
                elif cur_start == date(today_d.year - 3, today_d.month, today_d.day):
                    default_p_idx = 2
                elif cur_start == date(today_d.year - 5, today_d.month, today_d.day):
                    default_p_idx = 3
                else:
                    default_p_idx = 4

                chosen_preset = st.radio(
                    "快捷週期",
                    period_presets,
                    index=default_p_idx,
                    key="sidebar_period_preset_radio",
                    on_change=_on_period_preset_change,
                    label_visibility="collapsed",
                )

                st.markdown('<div style="margin-top: 8px;"></div>', unsafe_allow_html=True)
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.date_input("開始日期", key="custom_date_start")
                with col_d2:
                    st.date_input("結束日期", key="custom_date_end")

                st.markdown("##### 🎛️ **策略細部參數**")
                for k, v in sig.parameters.items():
                    if k == "self" or v.default is inspect.Parameter.empty:
                        continue
                    default = v.default
                    if isinstance(default, bool):
                        strategy_params[k] = st.checkbox(k, value=default, key=f"param_{k}")
                    elif isinstance(default, int):
                        strategy_params[k] = st.number_input(k, value=default, step=1, key=f"param_{k}")
                    elif isinstance(default, float):
                        strategy_params[k] = st.number_input(k, value=default, step=0.5, format="%.2f", key=f"param_{k}")
                    elif isinstance(default, str):
                        strategy_params[k] = st.text_input(k, value=default, key=f"param_{k}")

                st.markdown("##### 🌐 **市場與快取**")
                market_opts = ["auto", "tw_listed", "tw_otc", "us"]
                cur_m_idx = market_opts.index(st.session_state.custom_market) if st.session_state.custom_market in market_opts else 0
                st.session_state.custom_market = st.selectbox(
                    "市場類型",
                    market_opts,
                    index=cur_m_idx,
                    help="auto 為系統自動判斷",
                )
                st.session_state.custom_force_refresh = st.checkbox(
                    "🔄 強制重抓最新還原權息資料",
                    value=st.session_state.custom_force_refresh,
                    help="若遇除權息或分割未同步，可勾選強制刷新本地快取",
                )

        start_date = st.session_state["custom_date_start"]
        end_date = st.session_state["custom_date_end"]
        market = st.session_state.custom_market
        force_refresh = st.session_state.custom_force_refresh

        st.markdown("")
        col_run1, col_run2 = st.columns([3, 1])
        with col_run1:
            run_btn = st.button("🚀 執行量化回測", use_container_width=True)
        with col_run2:
            if st.button("🔄", help="立即清空快取並重抓最新報價"):
                st.cache_data.clear()
                st.rerun()

    # ── 主畫面標題 ────────────────────────────────────────────────────
    st.markdown('<div class="hero-title">🔬 量化回測實驗室</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">支援除權息自動還原、多時間週期共振策略與精確資金模擬</div>', unsafe_allow_html=True)

    symbol = symbol.strip().upper()
    if not symbol:
        st.warning("⚠️ 請於左側面板輸入欲回測之股票代號（例如 0050、2330）。")
        st.stop()
    with st.spinner(f"正在載入 {symbol} 還原資料並執行「{selected_strategy}」策略運算..."):
        try:
            if force_refresh:
                st.cache_data.clear()
            df, is_cache = _load_data(symbol, start_date, end_date, market, force_refresh=force_refresh, cache_version=date.today().isoformat())
            if df.empty:
                st.error(f"❌ 查無代號 **{symbol}** 的行情數據，請確認代號正確性。")
                st.stop()

            result = _run_backtest(df, selected_strategy, strategy_params, float(capital), symbol)
            metrics = _get_metrics(result)

        except Exception as e:
            st.error(f"❌ 回測執行異常：{e}")
            st.stop()

    # ── 資料快取狀態橫幅 ──────────────────────────────────────────────
    if is_cache:
        st.markdown(
            f"<div style='background:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); border-radius:8px; padding:8px 14px; margin-bottom:16px; font-size:0.85rem;'>"
            f"⚡ <b>本地 SQLite 快取命中</b>：已自本地數據庫零延遲讀取 <code>{symbol}</code>（共 {len(df)} 筆日線資料），無須重複發送網路請求。"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background:rgba(56, 189, 248, 0.1); border:1px solid rgba(56, 189, 248, 0.3); border-radius:8px; padding:8px 14px; margin-bottom:16px; font-size:0.85rem;'>"
            f"🌐 <b>還原權息資料已下載</b>：已自網路取得 <code>{symbol}</code> 最新除權息還原行情，並永久儲存至本地 SQLite 快取庫。"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── 頂級 KPI 統計網格 ──────────────────────────────────────────────
    tot_ret = metrics["total_return_pct"]
    ann_ret = metrics["annualized_return_pct"]
    tot_pnl = metrics.get("total_pnl", result.final_capital - result.initial_capital)
    mdd = metrics["max_drawdown_pct"]
    sharpe = metrics["sharpe_ratio"]
    win_rate = metrics["win_rate_pct"]
    pf = metrics["profit_factor"]
    trades_cnt = metrics["total_trades"]

    # 買入持有基準對照 (以第一天收盤為基準)
    bh_final = result.initial_capital * (df["close"].iloc[-1] / df["close"].iloc[0])
    bh_ret = (bh_final / result.initial_capital - 1) * 100
    alpha = tot_ret - bh_ret

    if trades_cnt == 0:
        ret_status = "neutral"
        ret_sub = "未觸發進場 (持幣觀望)"
        alpha_sub = f"同期標的: {bh_ret:+.1f}%"
    else:
        ret_status = "pos" if tot_ret > 0 else ("neg" if tot_ret < 0 else "neutral")
        ret_sub = f"淨損益: ${tot_pnl:+,.0f}"
        alpha_sub = f"超額收益: {alpha:+.1f}%"

    kpi_html = f"""
    <div class="kpi-grid">
        {_render_kpi_card("策略總報酬率", f"{tot_ret:+.2f}%", ret_sub, ret_status)}
        {_render_kpi_card("買入持有同期", f"{bh_ret:+.2f}%", f"標的淨漲跌", "pos" if bh_ret>=0 else "neg")}
        {_render_kpi_card("年化報酬率", f"{ann_ret:+.2f}%", alpha_sub, "pos" if ann_ret>0 else ("neg" if ann_ret<0 else "neutral"))}
        {_render_kpi_card("最大回撤 (MDD)", f"{mdd:.2f}%", f"持倉修復: {metrics['max_drawdown_duration_days']} 天", "neg" if mdd<0 else "neutral")}
        {_render_kpi_card("Sharpe Ratio", f"{sharpe:.3f}" if abs(sharpe) < 100 else "0.000", "風險調整後回報", "pos" if sharpe>=1 else "neutral")}
        {_render_kpi_card("實盤成交", f"{trades_cnt} 筆", f"勝率: {win_rate:.1f}%", "pos" if win_rate>=50 and trades_cnt>0 else "neutral")}
        {_render_kpi_card("獲利因子 (PF)", f"{pf:.2f}" if (pf!=float('inf') and trades_cnt>0) else ("∞" if pf==float('inf') else "0.00"), "盈虧金額比", "pos" if pf>=1.5 else "neutral")}
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    if trades_cnt == 0:
        st.info(f"💡 **提示**：在指定回測期間內，`{selected_strategy}` 策略條件未被觸發，全程保持 100% 現金空倉（總資產維持本金 ${result.initial_capital:,.0f} 元，總報酬 0.00%）。若想增加進場頻率，可嘗試微調左側策略參數或擴大回測時間範圍。")

    import importlib
    import stock_backtester.dashboard.charts as charts_mod
    importlib.reload(charts_mod)
    plot_equity_curve = charts_mod.plot_equity_curve
    plot_candlestick_signals = charts_mod.plot_candlestick_signals
    plot_drawdown = charts_mod.plot_drawdown
    plot_monthly_returns_heatmap = charts_mod.plot_monthly_returns_heatmap
    plot_pnl_distribution = charts_mod.plot_pnl_distribution
    build_trades_df = charts_mod.build_trades_df
    plot_uninvested_entry_radar = charts_mod.plot_uninvested_entry_radar

    # ── 1. 資金成長走勢 (Equity Curve & Alpha) ─────────────────────────
    st.markdown("### 📈 1. 資金成長曲線 (Equity & Benchmark)")

    st.markdown("""
    <div class="info-hint-container">
        <div class="info-hint-pill">
            <span style="color: #38BDF8; font-size: 14px;">●</span>
            <b>策略資金</b>
            <span class="info-hint-icon">ⓘ</span>
            <div class="info-hint-tooltip">
                <b style="color: #38BDF8; font-size: 0.85rem;">📈 策略資金 (Strategy Equity)</b><br>
                代表完全依照該<b>量化策略訊號</b>買賣操作時的每日總資產淨值（現金餘額＋持股市值）。<br>
                • <b>買進持股時</b>：資產跟隨標的波段獲利同步增長。<br>
                • <b>停利出場時</b>：全額換回現金停泊避險，不受市場後續回檔影響。
            </div>
        </div>
        <div class="info-hint-pill">
            <span style="color: #94A3B8; font-size: 14px;">⋯</span>
            <b>基準資金</b>
            <span class="info-hint-icon">ⓘ</span>
            <div class="info-hint-tooltip">
                <b style="color: #94A3B8; font-size: 0.85rem;">🏦 基準資金 (Benchmark / 買入持有)</b><br>
                代表在回測第 1 天將全部本金買進該檔股票，並且<b>全程死抱不賣（Buy & Hold）</b>的每日資產價值。<br>
                • 這是評估量化策略是否具備價值的最關鍵<b>比較基準</b>。<br>
                • 策略資金高於基準資金的差距即為 <b>Alpha 超額報酬</b>。
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.plotly_chart(plot_equity_curve(result), use_container_width=True)

    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        st.metric(
            "策略最終資金",
            f"${result.final_capital:,.0f} TWD",
            delta=f"{result.final_capital - result.initial_capital:+,.0f} TWD",
            help="💡 策略資金：依照量化指標訊號進出場的即時總資產（現金+持股）。在空頭時保留現金避險，在多頭時捕捉主升段獲利。",
        )
    with col_e2:
        st.metric(
            "基準資金 (買入持有)",
            f"${bh_final:,.0f} TWD",
            delta=f"{bh_ret:+.2f}%",
            help="💡 基準資金（Benchmark）：回測首日將本金全額買進該標的並一路抱牢不賣（Buy & Hold）的資金淨值。用以衡量策略是否戰勝市場被動持有。",
        )
    with col_e3:
        st.metric(
            "策略 Alpha (超額表現)",
            f"{alpha:+.2f}%",
            delta=f"{alpha:+.2f}%",
            delta_color="normal",
            help="💡 Alpha（超額報酬）：策略總報酬率減去基準資金買入持有總報酬率。正數代表策略績效大幅打敗無腦死抱！",
        )

    st.markdown("---")

    # ── 2. 行情 K 線走勢與買賣訊號 ────────────────────────────────────
    st.markdown(f"### 🏷️ 2. 標的價格資訊與行情圖表 ── {result.symbol}")

    # 即時價格摘要列 (Price Cards)
    cur_p = result.data["close"].iloc[-1]
    prev_p = result.data["close"].iloc[-2] if len(result.data) > 1 else cur_p
    p_change = cur_p - prev_p
    p_change_pct = (p_change / prev_p) * 100 if prev_p > 0 else 0
    p_high = result.data["high"].max()
    p_low = result.data["low"].min()
    period_chg_pct = ((cur_p - result.data["close"].iloc[0]) / result.data["close"].iloc[0]) * 100
    latest_vol = result.data["volume"].iloc[-1]

    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    with p_col1:
        st.metric("標的最新收盤價", f"${cur_p:.2f} TWD", f"{p_change:+.2f} ({p_change_pct:+.2f}%)")
    with p_col2:
        st.metric("期間累計漲跌幅", f"{period_chg_pct:+.2f}%", help="回測期間內標的股價買入持有累計漲跌幅")
    with p_col3:
        st.metric("期間最高 / 最低價", f"${p_high:.2f} / ${p_low:.2f}", help="回測區間內標的震盪最高價與最低價")
    with p_col4:
        st.metric("最新單日成交量", f"{latest_vol:,.0f} 股", help="最新交易日成交股數")

    tab_kline_bt, tab_entry_radar = st.tabs([
        "🕯️ 策略回測完整行情圖 (含歷史買賣標籤與結算)",
        "🎯 空手進場專屬獨立圖表 (突破目標線與季線防守)",
    ])

    with tab_kline_bt:
        st.markdown("##### 🎚️ 行情時間軸控制與區間平移 (Slide Bar)")
        col_tf1, col_tf2, col_tf3 = st.columns([3.2, 1.2, 2.6])
        with col_tf1:
            timeframe = st.radio(
                "時間週期切換",
                ["☀️ 日線 (1D)", "📅 週線 (1W)", "🌕 月線 (1M)", "⏱️ 自訂天數 (N-Day)"],
                index=0,
                horizontal=True,
                label_visibility="collapsed",
                key="chart_timeframe_selector",
            )
        with col_tf2:
            if "自訂天數" in timeframe:
                n_days = st.number_input("天數", min_value=2, max_value=60, value=3, step=1, label_visibility="collapsed", key="custom_n_days_input")
            else:
                n_days = 3
        with col_tf3:
            window_choice = st.selectbox(
                "固定檢視區間",
                [
                    "🌐 隨回測區間完整展開 (自動同步回測起訖)",
                    "📐 局部聚焦 30 根 K 線 (約 1.5 個月 - 聚焦短線)",
                    "📐 局部聚焦 60 根 K 線 (約 1 季)",
                    "📐 局部聚焦 90 根 K 線 (約 4.5 個月)",
                    "📐 局部聚焦 120 根 K 線 (約半年)",
                    "📐 局部聚焦 240 根 K 線 (約 1 年)",
                ],
                index=0,
                label_visibility="collapsed",
                help="預設自動隨左側回測區間完整展開。亦可切換為局部固定視窗並使用滑桿平移。",
                key="kline_window_choice",
            )

        # 聚合計算當前週期總 K 棒數與時間索引
        if "1W" in timeframe or "週" in timeframe:
            sub_idx = result.data.resample("W-FRI").last().dropna().index
        elif "1M" in timeframe or "月" in timeframe:
            sub_idx = result.data.resample("ME").last().dropna().index
        elif "自訂天數" in timeframe:
            chunks = [result.data.iloc[i:i+n_days] for i in range(0, len(result.data), n_days) if len(result.data.iloc[i:i+n_days]) > 0]
            sub_idx = pd.DatetimeIndex([c.index[-1] for c in chunks])
        else:
            sub_idx = result.data.index

        n_bars = len(sub_idx)
        window_map = {
            "📐 局部聚焦 30 根 K 線 (約 1.5 個月 - 聚焦短線)": 30,
            "📐 局部聚焦 60 根 K 線 (約 1 季)": 60,
            "📐 局部聚焦 90 根 K 線 (約 4.5 個月)": 90,
            "📐 局部聚焦 120 根 K 線 (約半年)": 120,
            "📐 局部聚焦 240 根 K 線 (約 1 年)": 240,
        }
        window_size = window_map.get(window_choice, None)

        visible_range = None
        if window_size is not None and n_bars > window_size:
            max_offset = n_bars - window_size
            slider_offset = st.slider(
                "🎚️ **時間軸固定區間滑動條 (Slide Bar)**",
                min_value=0,
                max_value=max_offset,
                value=max_offset,
                help="拖曳滑動條即可固定此區間平移！圖表底部的時間軸也支援直接拖曳左右滑動。",
                key="kline_window_slider",
            )
            v_start = sub_idx[slider_offset]
            v_end = sub_idx[slider_offset + window_size - 1]
            visible_range = (v_start, v_end)
            st.caption(f"📍 局部聚焦：`{v_start.strftime('%Y-%m-%d')}` ～ `{v_end.strftime('%Y-%m-%d')}`（{window_size} 根 K 棒，支援滑桿平移）")
        else:
            # 隨回測區間完整展開：起訖精準對齊回測範圍
            if n_bars > 0:
                visible_range = (sub_idx[0], sub_idx[-1])
                st.caption(f"📍 K 線回測完整區間：`{sub_idx[0].strftime('%Y-%m-%d')}` ～ `{sub_idx[-1].strftime('%Y-%m-%d')}`（共 **{n_bars}** 根 K 棒，圖表底部滑動條支援自由縮放）")
            else:
                st.caption("💡 支援圖表滑動條平移與滾輪縮放。")

        st.plotly_chart(
            plot_candlestick_signals(
                result,
                timeframe=timeframe,
                n_days=n_days,
                visible_range=visible_range,
                show_rangeslider=True,
            ),
            use_container_width=True,
        )
        st.caption(f"💡 ▲ 買 / ▼ 賣標記（共 {len(result.trades)} 筆成交），懸停可檢視成交損益明細。")
        st.caption("✨ **K 線價格軸具備動態自適應縮放**：當拖曳底部時間軸滑桿或使用滾輪放大縮小特定時段時，價格 Y 軸與成交量高度將自動即時貼合該可視區間的高低點，徹底杜絕畫面扁平。")

        # ── 注入 K 線價格軸即時動態自適應縮放腳本 (Dynamic Y-axis Auto-Scaler) ──
        components.html(
            """
            <script>
            (function() {
                let parentDoc = null;
                try {
                    parentDoc = window.parent.document;
                } catch (e) {
                    return;
                }

                function findKlinePlot() {
                    if (!parentDoc) return null;
                    const plots = Array.from(parentDoc.querySelectorAll('.js-plotly-plot'));
                    return plots.find(p => p.data && p.data.some(d => d.type === 'candlestick'));
                }

                function setupScaler() {
                    const plot = findKlinePlot();
                    if (!plot || !plot._fullData || plot._fullData.length === 0) {
                        return false;
                    }

                    // 唯一標識，確保每次頁面重繪時最新 handler 生效
                    const handlerId = Math.random().toString(36).substring(2);
                    plot.__kline_scaler_id = handlerId;

                    let isRelayouting = false;
                    let debounceTimer = null;

                    function rescaleToVisibleRange(x0, x1) {
                        if (isRelayouting) return;
                        if (plot.__kline_scaler_id !== handlerId) return;

                        const fd = plot._fullData;
                        if (!fd || fd.length === 0) return;

                        const candTrace = fd.find(t => t.type === 'candlestick');
                        if (!candTrace || !candTrace.x || candTrace.x.length === 0) return;

                        let t0 = new Date(x0).getTime();
                        let t1 = new Date(x1).getTime();
                        if (isNaN(t0) || isNaN(t1)) return;
                        if (t0 > t1) { const tmp = t0; t0 = t1; t1 = tmp; }

                        // 主圖價格 trace (Row 1: yaxis 為 'y' 或未指定)
                        const priceTraces = fd.filter(t => !t.yaxis || t.yaxis === 'y');
                        let minY = Infinity, maxY = -Infinity;

                        for (const t of priceTraces) {
                            if (!t.x) continue;
                            for (let i = 0; i < t.x.length; i++) {
                                const time = new Date(t.x[i]).getTime();
                                if (time >= t0 && time <= t1) {
                                    if (t.type === 'candlestick') {
                                        if (t.low && t.low[i] < minY) minY = t.low[i];
                                        if (t.high && t.high[i] > maxY) maxY = t.high[i];
                                    } else if (t.y && t.y[i] != null && !isNaN(t.y[i])) {
                                        if (t.y[i] < minY) minY = t.y[i];
                                        if (t.y[i] > maxY) maxY = t.y[i];
                                    }
                                }
                            }
                        }

                        if (minY === Infinity || maxY === -Infinity || minY >= maxY) return;

                        // 8% 垂直安全留白，避免燭芯被裁切
                        const pad = (maxY - minY) * 0.08;
                        const newYRange = [Math.max(0, minY - pad), maxY + pad];

                        // 可視區間成交量自適應
                        let maxVol = 0;
                        const volTrace = fd.find(t => t.type === 'bar' && (t.yaxis === 'y2' || !t.yaxis));
                        if (volTrace && volTrace.x && volTrace.y) {
                            for (let i = 0; i < volTrace.x.length; i++) {
                                const time = new Date(volTrace.x[i]).getTime();
                                if (time >= t0 && time <= t1) {
                                    if (volTrace.y[i] > maxVol) maxVol = volTrace.y[i];
                                }
                            }
                        }

                        const relayoutUpdate = {
                            'yaxis.range': newYRange,
                            'yaxis.autorange': false
                        };
                        if (maxVol > 0) {
                            relayoutUpdate['yaxis2.range'] = [0, maxVol * 1.15];
                            relayoutUpdate['yaxis2.autorange'] = false;
                        }

                        isRelayouting = true;
                        if (window.parent.Plotly && typeof window.parent.Plotly.relayout === 'function') {
                            window.parent.Plotly.relayout(plot, relayoutUpdate).then(() => {
                                isRelayouting = false;
                            }).catch(() => {
                                isRelayouting = false;
                            });
                        } else {
                            isRelayouting = false;
                        }
                    }

                    plot.on('plotly_relayout', function(ed) {
                        if (isRelayouting) return;
                        if (plot.__kline_scaler_id !== handlerId) return;

                        const hasX = ('xaxis.range[0]' in ed) || ('xaxis.range' in ed) || ('xaxis.autorange' in ed);
                        if (!hasX) return;

                        let x0 = ed['xaxis.range[0]'] || (ed['xaxis.range'] && ed['xaxis.range'][0]);
                        let x1 = ed['xaxis.range[1]'] || (ed['xaxis.range'] && ed['xaxis.range'][1]);

                        if (ed['xaxis.autorange'] || !x0 || !x1) {
                            const candTrace = plot._fullData.find(t => t.type === 'candlestick');
                            if (candTrace && candTrace.x) {
                                x0 = candTrace.x[0];
                                x1 = candTrace.x[candTrace.x.length - 1];
                            }
                        }

                        if (x0 && x1) {
                            clearTimeout(debounceTimer);
                            debounceTimer = setTimeout(() => rescaleToVisibleRange(x0, x1), 25);
                        }
                    });

                    // 初始載入時若已有可視範圍，立即自適應貼合
                    const currX = plot.layout.xaxis ? plot.layout.xaxis.range : null;
                    if (currX && currX.length === 2) {
                        rescaleToVisibleRange(currX[0], currX[1]);
                    }

                    return true;
                }

                let count = 0;
                const poller = setInterval(() => {
                    count++;
                    if (setupScaler() || count > 40) {
                        clearInterval(poller);
                    }
                }, 100);
            })();
            </script>
            """,
            height=0,
        )

    with tab_entry_radar:
        # ── 額外獨立專屬圖表：空手等待進場點即時監控雷達 ──
        st.plotly_chart(
            plot_uninvested_entry_radar(symbol, result.data),
            use_container_width=True,
        )

        # ── 空手進場點即時監控雷達卡片 (Uninvested Entry Radar) ──
        latest_c = float(result.data["close"].iloc[-1])
        latest_o = float(result.data["open"].iloc[-1])
        ma60_val = float(result.data["close"].rolling(60, min_periods=1).mean().iloc[-1])
        bias_val = ((latest_c - ma60_val) / ma60_val) * 100
        roll_20_h = float(result.data["high"].rolling(20, min_periods=1).max().shift(1).iloc[-1]) if len(result.data) >= 20 else float(result.data["high"].max())
        capitulation_p = ma60_val * 0.94
        dist_breakout = roll_20_h - latest_c
        pct_breakout = (dist_breakout / latest_c) * 100

        is_breakout = (latest_c > roll_20_h and bias_val > 0)
        # 計算三大抄底梯隊門檻
        pullback_min_p = ma60_val * 0.98
        pullback_max_p = ma60_val * 1.01
        is_pullback = (-2.0 <= bias_val <= 1.0) and (latest_c > latest_o)
        dist_pullback = latest_c - pullback_max_p
        pct_pullback = (dist_pullback / latest_c) * 100

        tier2_max_p = roll_20_h * 0.92
        tier2_min_p = roll_20_h * 0.90
        is_tier2 = (tier2_min_p <= latest_c <= tier2_max_p) and (latest_c > latest_o)
        dist_tier2 = latest_c - tier2_max_p
        pct_tier2 = (dist_tier2 / latest_c) * 100

        is_breakout = (latest_c > roll_20_h and bias_val > 0)
        is_panic = (bias_val <= -6.0 and latest_c > latest_o)

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%); 
                        border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 12px; padding: 1.1rem 1.4rem; margin: 0.8rem 0 1.2rem 0;
                        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                    <span style="font-size: 1.05rem; font-weight: 700; color: #38BDF8; letter-spacing: 0.5px;">
                        🎯 空手投資人專屬 ── 三大抄底梯隊與右側突破即時雷達
                    </span>
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; padding: 3px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(56, 189, 248, 0.3);">
                        ● 實時雷達監控中
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.85rem; margin-top: 0.6rem;">
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.85rem; border-radius: 8px; border: 1px solid rgba(34, 197, 94, 0.25);">
                        <div style="font-size: 0.8rem; color: #94A3B8;">🚀 右側強勢突破點</div>
                        <div style="font-size: 1.35rem; font-weight: 700; color: #22C55E; margin: 3px 0;">${roll_20_h:.2f}</div>
                        <div style="font-size: 0.76rem; color: #CBD5E1;">距突破僅差 <b style="color: #22C55E;">+{pct_breakout:.2f}%</b> (差 {dist_breakout:+.2f} 元)</div>
                        <div style="font-size: 0.7rem; color: #64748B; margin-top: 4px;">突破 20 日高點順勢追價</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.85rem; border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.25);">
                        <div style="font-size: 0.8rem; color: #94A3B8;">🎯 第一梯隊：季線回踩區</div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #38BDF8; margin: 3px 0;">${pullback_min_p:.2f} ~ ${pullback_max_p:.2f}</div>
                        <div style="font-size: 0.76rem; color: #CBD5E1;">拉回 <b style="color: #38BDF8;">{pct_pullback:.2f}%</b> (約差 {dist_pullback:.2f} 元) 進區間</div>
                        <div style="font-size: 0.7rem; color: #38BDF8; margin-top: 4px;">🌟 季線 -2%~+1% 守穩紅K (勝率 81%)</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.85rem; border-radius: 8px; border: 1px solid rgba(192, 132, 252, 0.25);">
                        <div style="font-size: 0.8rem; color: #94A3B8;">🌟 第二梯隊：波段黃金區</div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #C084FC; margin: 3px 0;">${tier2_min_p:.2f} ~ ${tier2_max_p:.2f}</div>
                        <div style="font-size: 0.76rem; color: #CBD5E1;">距前高拉回 <b>-8% ~ -10%</b> (差 {dist_tier2:.2f} 元)</div>
                        <div style="font-size: 0.7rem; color: #C084FC; margin-top: 4px;">百元大關強支撐 (勝率 77%~93%)</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.85rem; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.25);">
                        <div style="font-size: 0.8rem; color: #94A3B8;">🛡️ 第三梯隊：極度恐慌點</div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #EF4444; margin: 3px 0;">&le; ${capitulation_p:.2f}</div>
                        <div style="font-size: 0.76rem; color: #CBD5E1;">需拉回 <b>{((latest_c - capitulation_p)/latest_c)*100:.2f}%</b> 觸發</div>
                        <div style="font-size: 0.7rem; color: #EF4444; margin-top: 4px;">季線負乖離 &le; -6% (勝率 84%, 均報酬+14%)</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Telegram 即時推播設定與測試
        with st.expander("🔔 Telegram 手機即時推播連動設定 (通知你抄底與突破)"):
            st.markdown("""
            **連動 Telegram 機器人即時推播步驟**：
            1. 在 Telegram 搜尋 `@BotFather` 輸入 `/newbot` 建立機器人，取得 `TELEGRAM_BOT_TOKEN`。
            2. 對您的機器人傳送任意訊息後，透過 `https://api.telegram.org/bot<TOKEN>/getUpdates` 取得 `chat_id`。
            3. 在下方直接輸入憑證並點擊儲存，滿足任一抄底梯隊或突破條件時即可收到推播！
            """)

            env_p = ROOT / ".env"
            saved_token, saved_chat_id = "", ""
            if env_p.exists():
                for line in env_p.read_text().splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        k, _, v = line.partition("=")
                        if k.strip() == "TELEGRAM_BOT_TOKEN": saved_token = v.strip()
                        elif k.strip() == "TELEGRAM_CHAT_ID": saved_chat_id = v.strip()

            col_tg1, col_tg2 = st.columns(2)
            with col_tg1:
                input_token = st.text_input("TELEGRAM_BOT_TOKEN", value=saved_token if saved_token != "your_bot_token_here" else "", type="password", help="例如: 123456789:ABCdefGhIJKlmNoPQRstuVWXyz")
            with col_tg2:
                input_chat_id = st.text_input("TELEGRAM_CHAT_ID", value=saved_chat_id if saved_chat_id != "your_chat_id_here" else "", help="例如: 987654321")

            col_btn1, col_btn2 = st.columns([1, 2])
            with col_btn1:
                if st.button("💾 儲存設定並測試發送", key="btn_save_and_test_tg"):
                    if input_token and input_chat_id:
                        env_content = f"TELEGRAM_BOT_TOKEN={input_token.strip()}\nTELEGRAM_CHAT_ID={input_chat_id.strip()}\n"
                        env_p.write_text(env_content, encoding="utf-8")
                        try:
                            from stock_backtester.notifiers.telegram_notifier import TelegramNotifier
                            notifier = TelegramNotifier(token=input_token.strip(), chat_id=input_chat_id.strip())
                            quote_url = f"https://tw.stock.yahoo.com/quote/{symbol}.TW"
                            test_msg = (
                                f"🎯 <b>{symbol} 空手進場雷達已連線！</b>\n\n"
                                f"📊 <b>最新行情與雷達價位：</b>\n"
                                f"• 現價：<a href='{quote_url}'><b>{latest_c:.2f} 元</b></a> (季線乖離 {bias_val:+.2f}%)\n"
                                f"• 🚀 <b>右側強勢突破價</b>：<a href='{quote_url}'><b>{roll_20_h:.2f} 元</b></a> (差 {dist_breakout:+.2f} 元 / +{pct_breakout:.2f}%)\n"
                                f"• 🎯 <b>第一梯隊(季線回踩)</b>：<a href='{quote_url}'><b>{pullback_min_p:.2f} ~ {pullback_max_p:.2f} 元</b></a> (差 {dist_pullback:+.2f} 元)\n"
                                f"• 🌟 <b>第二梯隊(波段黃金)</b>：<a href='{quote_url}'><b>{tier2_min_p:.2f} ~ {tier2_max_p:.2f} 元</b></a> (距高點 -8%~-10%)\n"
                                f"• 🛡️ <b>第三梯隊(恐慌超跌)</b>：≤ <a href='{quote_url}'><b>{capitulation_p:.2f} 元</b></a> (季線負乖離 ≤ -6%)\n\n"
                                f"⏳ <b>狀態</b>：實時監控中，滿足任一條件立即推播通知！"
                            )
                            if notifier.send(test_msg):
                                st.success("✅ Telegram 憑證已成功儲存至 `.env`，並成功發送測試通知！請查看手機 Telegram。")
                            else:
                                st.error("❌ 發送失敗，請檢查 Token 與 Chat ID 是否正確。")
                        except Exception as e:
                            st.error(f"❌ 發送異常: {e}")
                    else:
                        st.warning("⚠️ 請完整輸入 Token 與 Chat ID。")
            with col_btn2:
                st.caption("💡 設定完成後，亦可透過終端機背景定時執行：`python3 -m stock_backtester.cli watch-entry --stock 0050 --notify`")

    st.markdown("---")

    # ── 3. 月度報酬熱力矩陣 ──────────────────────────────────────────
    heat_fig = plot_monthly_returns_heatmap(result)
    if heat_fig.data:
        st.markdown("### 🗓️ 3. 月度報酬熱力矩陣 (Monthly Returns %)")
        st.plotly_chart(heat_fig, use_container_width=True)
        st.caption("💡 綠色代表當月獲利，紅色代表當月虧損。數值為該月份的淨報酬百分比。")
        st.markdown("---")

    # ── 4. 水下回撤風險分析 ──────────────────────────────────────────
    st.markdown("### 📉 4. 水下回撤風險走勢 (Drawdown)")
    st.plotly_chart(plot_drawdown(result), use_container_width=True)
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.metric("歷史最大資產回撤 (MDD)", f"{mdd:.2f}%")
    with col_r2:
        st.metric("最長水下修復天數", f"{metrics['max_drawdown_duration_days']} 天")

    st.markdown("---")

    # ── 5. 單筆損益與交易明細 ────────────────────────────────────────
    st.markdown("### 📊 5. 單筆交易損益與成交明細")
    trades_df = build_trades_df(result)
    if trades_df.empty:
        st.info("回測區間內無已平倉的交易紀錄。")
    else:
        wins = sum(1 for t in result.trades if t.pnl > 0)
        total = len(result.trades)

        col_w1, col_w2 = st.columns([1, 3])
        with col_w1:
            st.metric("實盤交易勝率", f"{win_rate:.1f}%", f"{wins}/{total} 筆獲利")
        with col_w2:
            st.markdown("<div style='padding-top:10px;'></div>", unsafe_allow_html=True)
            st.progress(wins / total)

        # 逐筆損益長條圖
        st.plotly_chart(plot_pnl_distribution(result), use_container_width=True)

        st.markdown("##### 📝 逐筆成交明細列表")
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

        csv_trades = trades_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇ 下載交易紀錄報表 (CSV)",
            data=csv_trades,
            file_name=f"{symbol}_{selected_strategy}_trades.csv",
            mime="text/csv",
        )

    st.markdown("---")

    # ── 6. 歷史行情數據庫預覽 ────────────────────────────────────────
    with st.expander(f"🗃️ 點擊展開查看 `{symbol}` 完整歷史還原行情數據 ({len(df)} 筆交易日)"):
        st.dataframe(
            df.tail(200).sort_index(ascending=False).style.format({
                "open": "{:.2f}", "high": "{:.2f}",
                "low": "{:.2f}", "close": "{:.2f}",
                "volume": "{:,.0f}",
            }),
            use_container_width=True,
            height=350,
        )
        csv_ohlcv = df.to_csv(encoding="utf-8-sig")
        st.download_button(
            "⬇ 下載完整 OHLCV 行情數據 (CSV)",
            data=csv_ohlcv,
            file_name=f"{symbol}_adjusted_ohlcv.csv",
            mime="text/csv",
        )


# ════════════════════════════════════════════════════════════════════════
# 🇺🇸 美股量化監控與進場雷達 (US Stock Radar View)
# ════════════════════════════════════════════════════════════════════════

elif page == "🇺🇸 美股量化監控與進場雷達":

    st.markdown('<div class="hero-title">🇺🇸 美股量化監控與進場雷達</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">抓取過去 10 年美股真實還原歷史行情，透過高勝率量化策略模型即時計算空手最佳進場梯隊與右側突破點。</div>', unsafe_allow_html=True)

    from stock_backtester.strategies import list_strategies, get_strategy

    with st.sidebar:
        st.markdown("#### 🇺🇸 **美股標的選擇**")
        us_options = ["(自訂輸入代號)"] + get_us_popular_options()
        _us_default_idx = min(1, len(us_options) - 1)  # 預設 NVDA，但防止越界
        selected_us = st.selectbox(
            "快捷美股標的",
            us_options,
            index=_us_default_idx,
            help="快速選擇熱門美股巨頭或科技 ETF (QQQ, SPY, SOXX 等)",
        )

        if selected_us != "(自訂輸入代號)":
            us_symbol = selected_us.split()[0]
            st.text_input("美股代號 (Symbol)", value=us_symbol, disabled=True)
        else:
            us_symbol = st.text_input("美股代號 (Symbol)", value="NVDA", help="輸入如 NVDA, AAPL, MSFT, QQQ, TSM").strip().upper()

        st.markdown("---")
        st.markdown("#### 🧠 **回測策略與評估模型**")
        all_strats = list_strategies()
        strat_opts = [s["name"] for s in all_strats]
        def_strat_idx = strat_opts.index("dip_hunter_alpha") if "dip_hunter_alpha" in strat_opts else 0
        chosen_strat_name = st.selectbox("選定參考策略", strat_opts, index=def_strat_idx)

        st.markdown("---")
        st.markdown("#### ⏳ **歷史資料長度**")
        hist_years = st.select_slider(
            "回測歷史跨度 (年)",
            options=[1, 3, 5, 10],
            value=10,
            help="系統預設載入過去 10 年完整還原股價進行長期量化壓力測試",
        )

        st.markdown("---")
        us_capital = st.number_input(
            "初始投資本金 (USD)",
            value=100_000,
            step=10_000,
            min_value=10_000,
        )

        st.markdown("")
        col_us_btn1, col_us_btn2 = st.columns([3, 1])
        with col_us_btn1:
            run_us_btn = st.button("🚀 執行美股雷達運算", use_container_width=True)
        with col_us_btn2:
            if st.button("🔄", help="立即清空快取並重抓最新報價", key="btn_clear_cache_us"):
                st.cache_data.clear()
                st.rerun()

    us_symbol = us_symbol.strip().upper()
    if not us_symbol:
        st.warning("⚠️ 請於左側輸入美股代號（例如 NVDA、AAPL、QQQ）。")
        st.stop()

    today_us = date.today()
    start_us = date(today_us.year - hist_years, today_us.month, today_us.day)

    with st.spinner(f"正在自 Yahoo Finance 抓取 {us_symbol} 過去 {hist_years} 年完整還原行情並進行量化運算..."):
        try:
            df_us, is_us_cached = _load_data(us_symbol, start_us, today_us, market="us", cache_version=f"us_{date.today().isoformat()}")
            if df_us.empty:
                st.error(f"❌ 查無美股代號 **{us_symbol}** 的行情數據，請確認代號正確性。")
                st.stop()

            # 確保資料清洗無 NaN
            df_us = df_us.dropna(subset=["open", "high", "low", "close"]).copy()
            df_us = df_us[(df_us["open"] > 0) & (df_us["close"] > 0)]

            # 執行回測引擎評估
            us_strat_cls = get_strategy(chosen_strat_name)
            us_strat_instance = us_strat_cls()
            from stock_backtester.engine.backtest_engine import BacktestEngine
            from stock_backtester.analysis.performance import PerformanceAnalyzer
            engine_us = BacktestEngine(initial_capital=float(us_capital))
            res_us = engine_us.run(df_us, us_strat_instance, symbol=us_symbol)
            metrics_us = PerformanceAnalyzer().analyze(res_us)

        except Exception as e:
            st.error(f"❌ 美股數據載入或運算異常: {e}")
            st.stop()

    # 頂部即時快取橫幅
    if is_us_cached:
        st.markdown(
            f"<div style='background:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); border-radius:8px; padding:8px 14px; margin-bottom:16px; font-size:0.85rem;'>"
            f"⚡ <b>本地 SQLite 快取命中</b>：已讀取 <code>{us_symbol}</code> 過去 {hist_years} 年歷史數據（共 {len(df_us)} 筆交易日），零延遲加載。"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background:rgba(56, 189, 248, 0.1); border:1px solid rgba(56, 189, 248, 0.3); border-radius:8px; padding:8px 14px; margin-bottom:16px; font-size:0.85rem;'>"
            f"🌐 <b>10 年歷史還原權息數據已載入</b>：已成功自 Yahoo Finance 下載 <code>{us_symbol}</code> 共 {len(df_us)} 筆交易日資料，並自動快取儲存。"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── 1. 美股即時報價卡片 (Quote Summary) ──
    latest_c_us = float(df_us["close"].iloc[-1])
    prev_c_us = float(df_us["close"].iloc[-2]) if len(df_us) > 1 else latest_c_us
    diff_us = latest_c_us - prev_c_us
    diff_pct_us = (diff_us / prev_c_us) * 100 if prev_c_us > 0 else 0.0
    high_us = float(df_us["high"].max())
    low_us = float(df_us["low"].min())
    total_gain_10y = ((latest_c_us - df_us["close"].iloc[0]) / df_us["close"].iloc[0]) * 100

    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    with col_q1:
        st.metric(f"{us_symbol} 最新收盤價", f"${latest_c_us:.2f} USD", f"{diff_us:+.2f} ({diff_pct_us:+.2f}%)")
    with col_q2:
        st.metric(f"過去 {hist_years} 年標的累計漲幅", f"{total_gain_10y:+,.1f}%", help="標的自回測起點以來被動買入持有的總漲跌")
    with col_q3:
        st.metric(f"{hist_years} 年最高 / 最低價", f"${high_us:.2f} / ${low_us:.2f}")
    with col_q4:
        st.metric("最新單日成交股數", f"{df_us['volume'].iloc[-1]:,.0f} 股")

    st.markdown("---")

    # ── 2. 空手進場點四大策略梯隊計算 ──
    ma60_us = float(df_us["close"].rolling(60, min_periods=1).mean().iloc[-1])
    bias_us = ((latest_c_us - ma60_us) / ma60_us) * 100
    roll_20_h_us = float(df_us["high"].rolling(20, min_periods=1).max().shift(1).iloc[-1]) if len(df_us) >= 20 else float(df_us["high"].max())
    dist_breakout_us = roll_20_h_us - latest_c_us
    pct_breakout_us = (dist_breakout_us / latest_c_us) * 100

    # 第一梯隊：季線回踩區 (MA60 -2% ~ +1%)
    pullback_min_us = ma60_us * 0.98
    pullback_max_us = ma60_us * 1.01
    dist_pullback_us = latest_c_us - pullback_max_us
    pct_pullback_us = (dist_pullback_us / latest_c_us) * 100

    # 第二梯隊：波段黃金拉回區 (前高 -8% ~ -10%)
    tier2_max_us = roll_20_h_us * 0.92
    tier2_min_us = roll_20_h_us * 0.90
    dist_tier2_us = latest_c_us - tier2_max_us
    pct_tier2_us = (dist_tier2_us / latest_c_us) * 100

    # 第三梯隊：極度恐慌超跌線 (MA60 <= -6%)
    panic_p_us = ma60_us * 0.94
    dist_panic_us = latest_c_us - panic_p_us
    pct_panic_us = (dist_panic_us / latest_c_us) * 100

    # 評估當前空手最佳建議
    if latest_c_us >= roll_20_h_us:
        action_title = "🔥 觸發右側強勢突破！"
        action_desc = f"現價 ${latest_c_us:.2f} 已突破前 20 日高點 (${roll_20_h_us:.2f})，動能轉強，適合順勢追價或右側建倉。"
        action_badge_color = "#22C55E"
    elif pullback_min_us <= latest_c_us <= pullback_max_us:
        action_title = "🎯 進入第一梯隊【季線回踩區】！"
        action_desc = f"現價 ${latest_c_us:.2f} 處於季線防守區間 (${pullback_min_us:.2f} ~ ${pullback_max_us:.2f})，回測歷史守穩反彈勝率高達 81%！"
        action_badge_color = "#38BDF8"
    elif tier2_min_us <= latest_c_us <= tier2_max_us:
        action_title = "🌟 進入第二梯隊【波段黃金拉回區】！"
        action_desc = f"現價 ${latest_c_us:.2f} 已自前高拉回 8%~10% (${tier2_min_us:.2f} ~ ${tier2_max_us:.2f})，性價比極高，可逢低分批布局。"
        action_badge_color = "#C084FC"
    elif latest_c_us <= panic_p_us:
        action_title = "🛡️ 觸發第三梯隊【極度恐慌超跌區】！"
        action_desc = f"現價 ${latest_c_us:.2f} 季線負乖離達 {bias_us:.1f}%（低於 ${panic_p_us:.2f}），已進入歷史罕見的恐慌超跌買點！"
        action_badge_color = "#EF4444"
    else:
        if dist_breakout_us > 0 and dist_pullback_us > 0:
            if pct_breakout_us <= 3.0:
                action_title = "👀 逼近右側突破點（持幣觀察）"
                action_desc = f"距突破僅差 +{pct_breakout_us:.2f}% (${roll_20_h_us:.2f})，建議等待突破後順勢進場，或等待回踩季線。"
                action_badge_color = "#FBBF24"
            else:
                action_title = "⏳ 震盪整理區間（持幣耐心等待訊號）"
                action_desc = f"目前價格處於上升通道中段（距突破差 +{pct_breakout_us:.2f}%，距季線回踩差 {pct_pullback_us:.2f}%），建議空手靜待任一梯隊觸發。"
                action_badge_color = "#94A3B8"
        else:
            action_title = "⏳ 觀察震盪走勢"
            action_desc = "請觀察價格在各梯隊價位附近的價量支撐反應。"
            action_badge_color = "#94A3B8"

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%); 
                    border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 1.2rem 1.5rem; margin: 1rem 0;
                    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.6);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
                <span style="font-size: 1.15rem; font-weight: 700; color: #38BDF8;">
                    🎯 空手投資人美股最佳進場決策雷達 ── {us_symbol}
                </span>
                <span style="background: {action_badge_color}22; color: {action_badge_color}; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; border: 1px solid {action_badge_color}55;">
                    ● {action_title}
                </span>
            </div>
            <div style="font-size: 0.9rem; color: #E2E8F0; margin-bottom: 1rem; line-height: 1.5;">
                {action_desc}
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.9rem;">
                <div style="background: rgba(15, 23, 42, 0.7); padding: 0.9rem; border-radius: 8px; border: 1px solid rgba(34, 197, 94, 0.3);">
                    <div style="font-size: 0.8rem; color: #94A3B8;">🚀 右側強勢突破點</div>
                    <div style="font-size: 1.35rem; font-weight: 700; color: #22C55E; margin: 3px 0;">${roll_20_h_us:.2f}</div>
                    <div style="font-size: 0.76rem; color: #CBD5E1;">距突破差 <b style="color: #22C55E;">+{pct_breakout_us:.2f}%</b> (${dist_breakout_us:+.2f})</div>
                    <div style="font-size: 0.7rem; color: #64748B; margin-top: 4px;">帶量突破 20 日高點順勢建倉</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.7); padding: 0.9rem; border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.3);">
                    <div style="font-size: 0.8rem; color: #94A3B8;">🎯 第一梯隊：季線回踩區</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #38BDF8; margin: 3px 0;">${pullback_min_us:.2f} ~ ${pullback_max_us:.2f}</div>
                    <div style="font-size: 0.76rem; color: #CBD5E1;">距區間上限 <b style="color: #38BDF8;">{pct_pullback_us:+.2f}%</b> (${dist_pullback_us:+.2f})</div>
                    <div style="font-size: 0.7rem; color: #38BDF8; margin-top: 4px;">季線生命線附近回測有守</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.7); padding: 0.9rem; border-radius: 8px; border: 1px solid rgba(192, 132, 252, 0.3);">
                    <div style="font-size: 0.8rem; color: #94A3B8;">🌟 第二梯隊：波段黃金拉回區</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #C084FC; margin: 3px 0;">${tier2_min_us:.2f} ~ ${tier2_max_us:.2f}</div>
                    <div style="font-size: 0.76rem; color: #CBD5E1;">自高點拉回 -8% ~ -10%</div>
                    <div style="font-size: 0.7rem; color: #C084FC; margin-top: 4px;">強勢成長股常見健康回檔</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.7); padding: 0.9rem; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3);">
                    <div style="font-size: 0.8rem; color: #94A3B8;">🛡️ 第三梯隊：極度恐慌超跌線</div>
                    <div style="font-size: 1.35rem; font-weight: 700; color: #EF4444; margin: 3px 0;">&le; ${panic_p_us:.2f}</div>
                    <div style="font-size: 0.76rem; color: #CBD5E1;">距超跌線差 <b style="color: #EF4444;">{pct_panic_us:+.2f}%</b></div>
                    <div style="font-size: 0.7rem; color: #EF4444; margin-top: 4px;">季線負乖離 &le; -6% 貪婪抄底</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ── 3. 圖表展示：空手進場點即時雷達圖與 10 年回測資產曲線 ──
    tab_us_radar, tab_us_backtest, tab_us_data = st.tabs([
        "🎯 空手進場點即時監控雷達圖 (突破線與支撐階梯)",
        f"📈 過去 {hist_years} 年策略回測成長曲線與 Alpha",
        f"🗃️ {us_symbol} 完整歷史行情預覽",
    ])

    import stock_backtester.dashboard.charts as charts_mod
    plot_uninvested_entry_radar = charts_mod.plot_uninvested_entry_radar
    plot_equity_curve = charts_mod.plot_equity_curve
    plot_candlestick_signals = charts_mod.plot_candlestick_signals
    build_trades_df = charts_mod.build_trades_df

    with tab_us_radar:
        st.plotly_chart(
            plot_uninvested_entry_radar(us_symbol, df_us, currency="$"),
            use_container_width=True,
        )
        st.caption(f"💡 圖表標示 {us_symbol} 突破目標線、季線生命線 (MA60) 及三大抄底梯隊區間，可直接查看當前股價與各目標價位之距離。")

    with tab_us_backtest:
        tot_ret_us = metrics_us["total_return_pct"]
        ann_ret_us = metrics_us["annualized_return_pct"]
        mdd_us = metrics_us["max_drawdown_pct"]
        sharpe_us = metrics_us["sharpe_ratio"]
        trades_us = metrics_us["total_trades"]
        win_rate_us = metrics_us["win_rate_pct"]

        # 買入持有對照
        bh_final_us = res_us.initial_capital * (df_us["close"].iloc[-1] / df_us["close"].iloc[0])
        bh_ret_us = (bh_final_us / res_us.initial_capital - 1) * 100
        alpha_us = tot_ret_us - bh_ret_us

        kpi_us_html = f"""
        <div class="kpi-grid">
            {_render_kpi_card("策略總報酬率", f"{tot_ret_us:+.2f}%", f"淨損益: ${res_us.final_capital - res_us.initial_capital:+,.0f} USD", "pos" if tot_ret_us>0 else "neg")}
            {_render_kpi_card(f"買入持有 {hist_years} 年", f"{bh_ret_us:+.2f}%", f"最終: ${bh_final_us:,.0f} USD", "pos" if bh_ret_us>=0 else "neg")}
            {_render_kpi_card("年化報酬率 (CAGR)", f"{ann_ret_us:+.2f}%", f"超額 Alpha: {alpha_us:+.1f}%", "pos" if ann_ret_us>0 else "neg")}
            {_render_kpi_card("最大回撤 (MDD)", f"{mdd_us:.2f}%", f"修復: {metrics_us['max_drawdown_duration_days']} 天", "neg" if mdd_us<0 else "neutral")}
            {_render_kpi_card("Sharpe Ratio", f"{sharpe_us:.3f}" if abs(sharpe_us)<100 else "0.000", "風險調整回報", "pos" if sharpe_us>=1 else "neutral")}
            {_render_kpi_card("成交筆數與勝率", f"{trades_us} 筆", f"勝率: {win_rate_us:.1f}%", "pos" if win_rate_us>=50 and trades_us>0 else "neutral")}
        </div>
        """
        st.markdown(kpi_us_html, unsafe_allow_html=True)

        st.plotly_chart(plot_equity_curve(res_us), use_container_width=True)

        # 成交記錄明細表
        trades_us_df = build_trades_df(res_us)
        if not trades_us_df.empty:
            with st.expander(f"📝 展開查看 {us_symbol} 過去 {hist_years} 年共 {len(res_us.trades)} 筆交易記錄明細"):
                st.dataframe(trades_us_df, use_container_width=True, hide_index=True)

    with tab_us_data:
        st.dataframe(
            df_us.tail(200).sort_index(ascending=False).style.format({
                "open": "{:.2f}", "high": "{:.2f}",
                "low": "{:.2f}", "close": "{:.2f}",
                "volume": "{:,.0f}",
            }),
            use_container_width=True,
            height=350,
        )
        csv_us = df_us.to_csv(encoding="utf-8-sig")
        st.download_button(
            f"⬇ 下載 {us_symbol} 歷史數據 (CSV)",
            data=csv_us,
            file_name=f"{us_symbol}_{hist_years}y_ohlcv.csv",
            mime="text/csv",
        )

