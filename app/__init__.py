"""Application-layer entry points and runtime coordination exports.

Keep business rules in ``domain`` and infrastructure adapters in ``infra``.
"""

from .bootstrap import main
from .controller import AppController
from infra.telegram.command_bot import TelegramCommandBot
from services.runtime_state import RuntimeState
from services.scanner_commands import ScannerCommandService
from services.symbol_registry import SymbolRegistry

__all__ = [
    "AppController",
    "RuntimeState",
    "ScannerCommandService",
    "SymbolRegistry",
    "TelegramCommandBot",
    "main",
]
