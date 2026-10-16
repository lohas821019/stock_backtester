# 股票回測系統 Stock Backtester

可擴展的台股 + 美股回測框架，支援日線與分鐘線，並提供策略插件機制。

## 安裝

```bash
cd stock_backtester
python3 -m pip install -e ".[dev]"
```

## 資料來源（免費）

| 來源 | 說明 |
|------|------|
| TWSE API | 台灣上市股票日線（免費，無需帳號） |
| TPEX API | 台灣上櫃股票日線（免費，無需帳號） |
| yfinance | 台股 + 美股日線 / 分鐘線（免費，分鐘線限60天） |

## 快速上手

```bash
# 下載台積電 2024 年日線資料
python3 -m stock_backtester.cli fetch --stock 2330 --start 2024-01-01 --end 2024-12-31

# 下載美股 TSMC ADR
python3 -m stock_backtester.cli fetch --stock TSM --start 2024-01-01

# 執行均線交叉策略回測
python3 -m stock_backtester.cli backtest --stock 2330 --strategy ma_cross --start 2023-01-01 --end 2024-12-31

# 列出所有可用策略
python3 -m stock_backtester.cli list-strategies
```

## 新增自訂策略

在 `stock_backtester/strategies/` 目錄下建立新的 Python 檔案，繼承 `BaseStrategy`：

```python
# stock_backtester/strategies/my_strategy.py
from stock_backtester.strategies.base_strategy import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "我的自訂策略"

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        # 回傳 1(買進) / -1(賣出) / 0(持平)
        signal = pd.Series(0, index=data.index)
        # ... 你的策略邏輯
        return signal
```

系統會自動掃描並載入 `strategies/` 目錄下的所有策略，無需修改其他程式碼。

## 永豐金 API 串接（預留）

`data/fetchers/sinopac_fetcher.py` 已預留完整接口，待串接時：

```bash
# 1. 安裝 shioaji
python3 -m pip install -e ".[sinopac]"

# 2. 申請永豐金模擬帳號（免費）
#    https://www.sinotrade.com.tw/ec/20180901/

# 3. 編輯 sinopac_fetcher.py，填入 api_key / secret_key
#    並取消 TODO 區塊的 pass/raise 即可啟用
```

## 雲端全自動排程（GitHub Actions）

本系統所有自動化監控與掃描均已完整部署至 **GitHub Actions 雲端**，完全獨立於本機電腦，電腦關機或休眠皆能正常運作：

### 1. 0050 / 0052 盤中實時進場雷達 (`.github/workflows/intraday_radar.yml`)
- **啟動時間**：台股交易日每週一至週五 **08:35** 自動喚醒。
- **運行方式**：在 GitHub 雲端 runner 上啟動 **常駐守護進程 (Live Daemon)**，每 30 秒輪詢 TWSE MIS 撮合行情。
- **09:00:00**：開盤打卡，推播今日 20 日突破價、季線回踩區間等關鍵監控門檻。
- **09:00 ~ 13:30**：盤中碰價 30 秒內推播 Telegram 急報。
- **13:35:00**：收盤自動彙整當日行情總結並結束。
- **防禦機制**：內建防重複實例與逾期防禦（若任務延遲超過 13:45 則自動跳過，絕不於傍晚誤送）。

### 2. 每日盤後全市場選股掃描 (`.github/workflows/daily_scan.yml`)
- **啟動時間**：台股交易日每週一至週五 **15:10** 自動執行。
- **運行方式**：自證交所與 TPEX 抓取當日收盤全市場 50 檔成分股數據，計算均線交叉、週 KD 等策略訊號。
- **推播通知**：開跑發送靜音通知，若有買進訊號即時推播，掃描完畢發送當日全市場總結報表。

> 若需要由外部排程服務（例如 cron-job.org / Cloudflare Workers）在指定秒數呼叫，亦可直接使用 GitHub API 觸發 `workflow_dispatch`。


## 專案結構

```
stock_backtester/
├── data/
│   ├── fetchers/
│   │   ├── twse_fetcher.py     # 台股上市日線（TWSE）
│   │   ├── tpex_fetcher.py     # 台股上櫃日線（TPEX）
│   │   ├── yfinance_fetcher.py # 台股+美股日線/分鐘線
│   │   └── sinopac_fetcher.py  # 永豐金 API（預留，待串接）
│   └── storage/                # SQLite 快取
├── engine/                     # 回測引擎
├── strategies/                 # 策略插件目錄（持續新增）
├── indicators/                 # 技術指標
└── analysis/                   # 績效分析與報告
```
