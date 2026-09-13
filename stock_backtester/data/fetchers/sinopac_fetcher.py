"""
永豐金證券 API 抓取器（預留接口）

永豐金 API（SinoPac Securities）提供免費測試環境：
    官方文件：https://sinopacAPI.github.io/Shioaji/
    套件：    pip install shioaji

連線方式（正式環境 & 模擬環境皆免費申請）：
    模擬帳號申請：https://www.sinotrade.com.tw/ec/20180901/
    正式帳號：永豐金證券開戶後即可使用

此檔案已預留完整接口，待您串接時取消 TODO 的 pass/raise 即可。

目前狀態：STUB（尚未啟用，所有方法呼叫都會拋出 NotImplementedError）
"""

import logging
from datetime import date, timedelta

import pandas as pd

from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)


class SinopacFetcher(BaseFetcher):
    """
    永豐金證券 Shioaji API 資料抓取器。

    功能（串接後可用）：
        - 歷史 K 線（日線、分鐘線）
        - 即時 Tick 訂閱
        - 即時報價訂閱
        - 委託下單（正式 / 模擬帳號）

    安裝：
        pip install shioaji

    快速開始：
        import shioaji as sj
        api = sj.Shioaji(simulation=True)          # simulation=True 使用模擬帳號
        api.login(api_key="YOUR_API_KEY", secret_key="YOUR_SECRET_KEY")

    串接步驟：
        1. 安裝 shioaji：pip install shioaji
        2. 申請模擬帳號（免費）：https://www.sinotrade.com.tw/ec/20180901/
        3. 取得 API Key 與 Secret Key
        4. 在本檔案填入 api_key / secret_key，並實作 TODO 區塊
        5. 在 DataManager 中取消 SinopacFetcher 的註解

    官方文件：https://sinotrade.github.io/
    """

    source_name = "Sinopac"

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        simulation: bool = True,
    ):
        """
        Args:
            api_key:    永豐金 API Key
            secret_key: 永豐金 Secret Key
            simulation: True = 模擬帳號（預設），False = 正式帳號
        """
        self._api_key = api_key
        self._secret_key = secret_key
        self._simulation = simulation
        self._api = None  # shioaji.Shioaji 實例（連線後填入）

    # ──────────────────────────────────────────────────────────────────────────
    # 連線管理
    # ──────────────────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """
        連線永豐金 API。

        TODO: 取消下方 raise，填入正確的 api_key / secret_key 後即可啟用。
        """
        raise NotImplementedError(
            "[Sinopac] 尚未串接。請：\n"
            "  1. pip install shioaji\n"
            "  2. 申請模擬帳號：https://www.sinotrade.com.tw/ec/20180901/\n"
            "  3. 填入 api_key / secret_key 並實作 connect()"
        )

        # TODO: 取消下方註解並填入帳號資訊
        # try:
        #     import shioaji as sj
        # except ImportError:
        #     raise ImportError("請先安裝永豐金 API：pip install shioaji")
        #
        # self._api = sj.Shioaji(simulation=self._simulation)
        # self._api.login(
        #     api_key=self._api_key,
        #     secret_key=self._secret_key,
        # )
        # logger.info("[Sinopac] 連線成功（模擬模式: %s）", self._simulation)

    def disconnect(self) -> None:
        """斷線。"""
        if self._api is not None:
            # TODO: self._api.logout()
            self._api = None
            logger.info("[Sinopac] 已斷線")

    # ──────────────────────────────────────────────────────────────────────────
    # 歷史資料
    # ──────────────────────────────────────────────────────────────────────────

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        抓取歷史 K 線資料。

        Args:
            symbol:   股票代號，例如 "2330"
            start:    開始日期
            end:      結束日期
            interval: "1d" / "1min" / "5min" / "15min" / "60min"

        Returns:
            標準 OHLCV DataFrame

        TODO: 取消下方 raise 並實作資料抓取邏輯。
        """
        raise NotImplementedError(
            "[Sinopac] fetch() 尚未實作，請先呼叫 connect() 並完成串接。"
        )

        # TODO: 取消下方註解實作歷史 K 線
        # self._ensure_connected()
        #
        # # shioaji interval 映射
        # _interval_map = {
        #     "1d":   sj.constant.SecurityType.Stock,   # 日線用不同 API
        #     "1min": "1",
        #     "5min": "5",
        #     "15min":"15",
        #     "60min":"60",
        # }
        #
        # if interval == "1d":
        #     # 日線使用 fetch_historical_data
        #     contract = self._api.Contracts.Stocks[symbol]
        #     kbars = self._api.kbars(
        #         contract=contract,
        #         start=start.strftime("%Y-%m-%d"),
        #         end=end.strftime("%Y-%m-%d"),
        #     )
        #     df = pd.DataFrame({**kbars})
        #     df.index = pd.to_datetime(df["ts"])
        #     df = df.rename(columns={
        #         "Open":   "open",
        #         "High":   "high",
        #         "Low":    "low",
        #         "Close":  "close",
        #         "Volume": "volume",
        #     })
        # else:
        #     # 分鐘線
        #     sj_interval = _interval_map.get(interval, "1")
        #     contract = self._api.Contracts.Stocks[symbol]
        #     kbars = self._api.kbars(
        #         contract=contract,
        #         start=start.strftime("%Y-%m-%d"),
        #         end=end.strftime("%Y-%m-%d"),
        #     )
        #     df = pd.DataFrame({**kbars})
        #     df.index = pd.to_datetime(df["ts"])
        #
        # return self._normalize(df)

    # ──────────────────────────────────────────────────────────────────────────
    # 即時資料訂閱（串接後使用）
    # ──────────────────────────────────────────────────────────────────────────

    def subscribe_tick(self, symbol: str, callback) -> None:
        """
        訂閱即時 Tick 資料。

        Args:
            symbol:   股票代號
            callback: 收到新 Tick 時呼叫的 callback(exchange, tick)

        TODO: 取消下方 raise 並實作訂閱邏輯。
        """
        raise NotImplementedError("[Sinopac] subscribe_tick() 尚未實作")

        # TODO:
        # self._ensure_connected()
        #
        # @self._api.on_tick_stk_v1()
        # def tick_handler(exchange, tick):
        #     callback(exchange, tick)
        #
        # contract = self._api.Contracts.Stocks[symbol]
        # self._api.quote.subscribe(contract, quote_type=sj.constant.QuoteType.Tick)
        # logger.info("[Sinopac] 已訂閱 %s 即時 Tick", symbol)

    def subscribe_quote(self, symbol: str, callback) -> None:
        """
        訂閱即時最佳五檔報價。

        TODO: 取消下方 raise 並實作訂閱邏輯。
        """
        raise NotImplementedError("[Sinopac] subscribe_quote() 尚未實作")

        # TODO:
        # self._ensure_connected()
        # contract = self._api.Contracts.Stocks[symbol]
        # self._api.quote.subscribe(
        #     contract,
        #     quote_type=sj.constant.QuoteType.BidAsk,
        # )

    # ──────────────────────────────────────────────────────────────────────────
    # 下單（串接後使用）
    # ──────────────────────────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        action: str,   # "Buy" or "Sell"
        quantity: int,
        price: float | None = None,  # None = 市價單
    ) -> dict:
        """
        委託下單（模擬 / 正式帳號）。

        Args:
            symbol:   股票代號
            action:   "Buy" 或 "Sell"
            quantity: 股數（以張為單位，1 張 = 1000 股）
            price:    委託價格，None 為市價單

        TODO: 取消下方 raise 並實作下單邏輯。
        """
        raise NotImplementedError("[Sinopac] place_order() 尚未實作")

        # TODO:
        # self._ensure_connected()
        #
        # contract = self._api.Contracts.Stocks[symbol]
        # order = self._api.Order(
        #     price=price or 0,
        #     quantity=quantity,
        #     action=sj.constant.Action.Buy if action == "Buy" else sj.constant.Action.Sell,
        #     price_type=(
        #         sj.constant.StockPriceType.MKT if price is None
        #         else sj.constant.StockPriceType.LMT
        #     ),
        #     order_type=sj.constant.OrderType.ROD,
        # )
        # trade = self._api.place_order(contract, order)
        # return trade

    # ──────────────────────────────────────────────────────────────────────────
    # 內部工具
    # ──────────────────────────────────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        """確保已連線，若未連線則自動連線。"""
        if self._api is None:
            self.connect()
