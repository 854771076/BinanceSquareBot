# src/binance_square_bot/services/__init__.py
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "StorageService": ".storage",
    "FnSource": ".source",
    "PolymarketSource": ".source",
    "BinanceTarget": ".target",
    "FnCliService": ".cli",
    "PolymarketCliService": ".cli",
    "CommonCliService": ".cli",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(_EXPORT_MODULES[name], __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
