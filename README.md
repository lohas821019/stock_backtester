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
