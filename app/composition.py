"""Application composition root.

Build concrete runtime services here so bootstrap and controller stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.runtime import ScannerEngine
from domain.engine import StrategyEngine
from infra.config import AppConfig
from infra.logging import StructuredLogger
from infra.mt5.gateway import MT5DataGateway
from infra.storage import SQLiteStore, StateManager
from infra.telegram import TelegramCommandBot, TelegramNotifier
from legacy.bridges.runtime_config import set_ob_fvg_mode
from services import AlertService, ScanService
from services.runtime_state import RuntimeState
from services.scanner_commands import ScannerCommandService
from services.symbol_registry import SymbolRegistry


@dataclass
class AppRuntime:
    config: AppConfig
    logger: StructuredLogger
    sqlite: SQLiteStore
    state_manager: StateManager
    data_gateway: MT5DataGateway
    symbol_registry: SymbolRegistry
    runtime_state: RuntimeState
    notifier: TelegramNotifier
    strategy: StrategyEngine
    alert_service: AlertService
    scan_service: ScanService
    engine: ScannerEngine
    scanner_service: ScannerCommandService
    telegram_bot: TelegramCommandBot


def build_app_runtime(config: AppConfig) -> AppRuntime:
    """Construct the concrete application runtime graph."""
    set_ob_fvg_mode(config.scanner.ob_fvg_mode)
    logger = StructuredLogger()
    sqlite = SQLiteStore()
    state_manager = StateManager(sqlite)
    data_gateway = MT5DataGateway(logger)
    symbol_registry = SymbolRegistry(config.scanner.symbols, config.scanner.symbol_aliases)
    runtime_state = RuntimeState(symbol_registry.get_all_symbols())
    notifier = TelegramNotifier(config.telegram, logger)
    strategy = StrategyEngine(
        htf_timeframes=config.scanner.htf_timeframes,
        confirmation_timeframes=config.scanner.confirmation_timeframes,
        confirmation_limit=config.scanner.confirmation_limit,
    )
    alert_service = AlertService(config, state_manager, notifier, logger)
    scan_service = ScanService(
        data_gateway=data_gateway,
        strategy_engine=strategy,
        state_manager=state_manager,
        alert_service=alert_service,
        logger=logger,
    )
    engine = ScannerEngine(
        config=config,
        data_gateway=data_gateway,
        notifier=notifier,
        state_manager=state_manager,
        scan_service=scan_service,
        logger=logger,
        runtime_state=runtime_state,
    )
    scanner_service = ScannerCommandService(
        engine=engine,
        symbol_registry=symbol_registry,
        runtime_state=runtime_state,
        logger=logger,
    )
    telegram_bot = TelegramCommandBot(
        config=config.telegram,
        notifier=notifier,
        symbol_registry=symbol_registry,
        scanner_service=scanner_service,
        logger=logger,
    )
    return AppRuntime(
        config=config,
        logger=logger,
        sqlite=sqlite,
        state_manager=state_manager,
        data_gateway=data_gateway,
        symbol_registry=symbol_registry,
        runtime_state=runtime_state,
        notifier=notifier,
        strategy=strategy,
        alert_service=alert_service,
        scan_service=scan_service,
        engine=engine,
        scanner_service=scanner_service,
        telegram_bot=telegram_bot,
    )
