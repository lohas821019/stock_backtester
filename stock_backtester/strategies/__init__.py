"""
策略自動載入機制（Strategy Registry）

自動掃描 strategies/ 目錄，載入所有繼承 BaseStrategy 的策略類別。
新增策略時只需建立新檔案，無需修改此 __init__.py。
"""

import importlib
import inspect
import logging
from pathlib import Path

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

# 策略登錄表：name -> class
_REGISTRY: dict[str, type[BaseStrategy]] = {}


def _auto_discover() -> None:
    """自動掃描並載入 strategies/ 目錄下所有策略。"""
    strategies_dir = Path(__file__).parent

    for py_file in strategies_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue  # 跳過 __init__.py、base_strategy.py 等

        module_name = f"stock_backtester.strategies.{py_file.stem}"

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning("[StrategyRegistry] 無法載入 %s: %s", module_name, e)
            continue

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                inspect.isclass(attr)
                and issubclass(attr, BaseStrategy)
                and attr is not BaseStrategy
                and not inspect.isabstract(attr)
            ):
                strategy_name = attr.name
                if strategy_name == "unnamed":
                    logger.warning(
                        "[StrategyRegistry] %s.name 未設定，跳過", attr.__name__
                    )
                    continue

                if strategy_name in _REGISTRY and _REGISTRY[strategy_name] != attr:
                    logger.warning(
                        "[StrategyRegistry] 策略名稱衝突: %s（%s vs %s），後者覆蓋前者",
                        strategy_name,
                        _REGISTRY[strategy_name].__name__,
                        attr.__name__,
                    )

                _REGISTRY[strategy_name] = attr
                logger.debug(
                    "[StrategyRegistry] 已載入策略: %s (%s)", strategy_name, attr.__name__
                )


def get_strategy(name: str) -> type[BaseStrategy]:
    """
    依名稱取得策略類別。

    Args:
        name: 策略名稱（BaseStrategy.name）

    Returns:
        策略類別（未實例化）

    Raises:
        KeyError: 若找不到指定策略
    """
    ALIASES = {
        "rsi": "daily_rsi",
        "monthly_kd": "monthly_kd_passivation",
    }
    target = ALIASES.get(name, name)

    if target not in _REGISTRY:
        _auto_discover()

    if target not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise KeyError(
            f"找不到策略: '{name}'。可用策略: {available}"
        )

    return _REGISTRY[target]


def list_strategies() -> list[dict]:
    """
    列出所有已載入的策略（動態即時掃描目錄中的新策略）。

    Returns:
        策略摘要清單 [{"name": ..., "description": ..., "class": ...}, ...]
    """
    _auto_discover()

    return [
        {
            "name": cls.name,
            "description": cls.description,
            "class": cls.__name__,
        }
        for cls in _REGISTRY.values()
    ]


def reload_strategies() -> None:
    """重新掃描並載入所有策略（開發時使用）。"""
    _REGISTRY.clear()
    _auto_discover()


# 模組載入時自動掃描
_auto_discover()
