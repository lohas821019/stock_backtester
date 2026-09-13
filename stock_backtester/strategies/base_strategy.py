"""
策略基底類別

所有策略必須繼承 BaseStrategy 並實作 generate_signals()。
系統會自動掃描 strategies/ 目錄，載入所有繼承 BaseStrategy 的類別。

如何新增策略：
    1. 在 strategies/ 目錄下建立新 .py 檔案
    2. 繼承 BaseStrategy
    3. 設定 name 和 description
    4. 實作 generate_signals(data) 方法
    5. 完成！系統會自動載入，不需修改其他程式碼。

範例：
    from stock_backtester.strategies.base_strategy import BaseStrategy
    import pandas as pd

    class MyStrategy(BaseStrategy):
        name = "my_strategy"
        description = "我的策略"

        def generate_signals(self, data: pd.DataFrame) -> pd.Series:
            signal = pd.Series(0, index=data.index)
            # 你的策略邏輯...
            return signal
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """
    策略抽象基底類別。

    Attributes:
        name:        策略唯一識別名稱（英文小寫底線）
        description: 策略說明
        params:      策略參數字典（可在 __init__ 中設定）
    """

    name: str = "unnamed"
    description: str = ""

    def __init__(self, **params):
        """
        初始化策略參數。

        子類別可覆寫 __init__ 並接受自訂參數，例如：
            def __init__(self, short_window=5, long_window=20):
                self.short_window = short_window
                self.long_window = long_window
        """
        self.params = params

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        根據歷史資料產生買賣訊號。

        Args:
            data: pd.DataFrame，columns=[open, high, low, close, volume]
                  index 為 DatetimeIndex（按時間升序排列）

        Returns:
            pd.Series，與 data 同 index，值為：
                 1  → 買進（做多）
                -1  → 賣出（做空 / 平多）
                 0  → 持平（不操作）

        注意：
            - 不要在此方法中使用未來資料（look-ahead bias）
            - 訊號代表「當日收盤時執行」的操作
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Strategy: {self.name}>"

    def summary(self) -> dict:
        """回傳策略摘要資訊。"""
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params,
        }
