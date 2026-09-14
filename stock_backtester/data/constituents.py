"""
台灣指數與成分股清單

提供元大台灣50 (0050) 以及其 50 檔成分股代號與中文名稱對照表。
可用於：
- 回測快速選股
- 每日入場點批次掃描
- Dashboard 下拉快速選單
"""

# 元大台灣 50 ETF 本身與全部 50 檔成分股
TAIWAN_50_STOCKS: list[dict[str, str]] = [
    {"symbol": "0050", "name": "元大台灣50 ETF"},
    {"symbol": "2330", "name": "台積電"},
    {"symbol": "2317", "name": "鴻海"},
    {"symbol": "2454", "name": "聯發科"},
    {"symbol": "2308", "name": "台達電"},
    {"symbol": "2382", "name": "廣達"},
    {"symbol": "2881", "name": "富邦金"},
    {"symbol": "2882", "name": "國泰金"},
    {"symbol": "2412", "name": "中華電"},
    {"symbol": "2303", "name": "聯電"},
    {"symbol": "2891", "name": "中信金"},
    {"symbol": "3711", "name": "日月光投控"},
    {"symbol": "2886", "name": "兆豐金"},
    {"symbol": "3231", "name": "緯創"},
    {"symbol": "6669", "name": "緯穎"},
    {"symbol": "2884", "name": "玉山金"},
    {"symbol": "2892", "name": "第一金"},
    {"symbol": "2885", "name": "元大金"},
    {"symbol": "2880", "name": "華南金"},
    {"symbol": "2887", "name": "台新金"},
    {"symbol": "2890", "name": "永豐金"},
    {"symbol": "1216", "name": "統一"},
    {"symbol": "1301", "name": "台塑"},
    {"symbol": "1303", "name": "南亞"},
    {"symbol": "2002", "name": "中鋼"},
    {"symbol": "5880", "name": "合庫金"},
    {"symbol": "2357", "name": "華碩"},
    {"symbol": "3008", "name": "大立光"},
    {"symbol": "2379", "name": "瑞昱"},
    {"symbol": "3045", "name": "台灣大"},
    {"symbol": "4904", "name": "遠傳"},
    {"symbol": "2395", "name": "研華"},
    {"symbol": "2603", "name": "長榮"},
    {"symbol": "2609", "name": "陽明"},
    {"symbol": "2615", "name": "萬海"},
    {"symbol": "2883", "name": "開發金(凱基金)"},
    {"symbol": "5871", "name": "中租-KY"},
    {"symbol": "2912", "name": "統一超"},
    {"symbol": "1101", "name": "台泥"},
    {"symbol": "2327", "name": "國巨"},
    {"symbol": "1326", "name": "台化"},
    {"symbol": "6505", "name": "台塑化"},
    {"symbol": "3034", "name": "聯詠"},
    {"symbol": "2207", "name": "和泰車"},
    {"symbol": "3037", "name": "欣興"},
    {"symbol": "3661", "name": "世芯-KY"},
    {"symbol": "2345", "name": "智邦"},
    {"symbol": "1590", "name": "亞德客-KY"},
    {"symbol": "2301", "name": "光寶科"},
    {"symbol": "2888", "name": "新光金"},
    {"symbol": "6415", "name": "矽力*-KY"},
]

# 快速字典查詢：symbol -> name
TAIWAN_50_MAP: dict[str, str] = {item["symbol"]: item["name"] for item in TAIWAN_50_STOCKS}


def get_taiwan_50_symbols() -> list[str]:
    """取得所有 0050 與成分股代號清單。"""
    return [item["symbol"] for item in TAIWAN_50_STOCKS]


def get_taiwan_50_options() -> list[str]:
    """取得格式化顯示選項（如 '2330 台積電'）。"""
    return [f"{item['symbol']} {item['name']}" for item in TAIWAN_50_STOCKS]


# ── 美股熱門指數 ETF 與科技權值股清單 ──────────────────────────────────
US_POPULAR_STOCKS: list[dict[str, str]] = [
    {"symbol": "NVDA", "name": "輝達 (NVIDIA)"},
    {"symbol": "AAPL", "name": "蘋果 (Apple)"},
    {"symbol": "MSFT", "name": "微軟 (Microsoft)"},
    {"symbol": "GOOGL", "name": "Alphabet (Google)"},
    {"symbol": "AMZN", "name": "亞馬遜 (Amazon)"},
    {"symbol": "TSLA", "name": "特斯拉 (Tesla)"},
    {"symbol": "META", "name": "Meta (Facebook)"},
    {"symbol": "TSM", "name": "台積電 ADR"},
    {"symbol": "AVGO", "name": "博通 (Broadcom)"},
    {"symbol": "AMD", "name": "超微 (AMD)"},
    {"symbol": "QQQ", "name": "那斯達克100 ETF (Invesco QQQ)"},
    {"symbol": "SPY", "name": "標普500 ETF (SPDR S&P 500)"},
    {"symbol": "SOXX", "name": "費城半導體 ETF (iShares)"},
    {"symbol": "SMH", "name": "VanEck 半導體 ETF"},
    {"symbol": "PLTR", "name": "Palantir"},
    {"symbol": "COIN", "name": "Coinbase"},
    {"symbol": "ARM", "name": "Arm Holdings"},
    {"symbol": "MU", "name": "美光科技 (Micron)"},
    {"symbol": "ASML", "name": "艾司摩爾 (ASML)"},
    {"symbol": "INTC", "name": "英特爾 (Intel)"},
]

US_POPULAR_MAP: dict[str, str] = {item["symbol"]: item["name"] for item in US_POPULAR_STOCKS}


def get_us_popular_options() -> list[str]:
    """取得美股熱門標的格式化清單。"""
    return [f"{item['symbol']} {item['name']}" for item in US_POPULAR_STOCKS]
