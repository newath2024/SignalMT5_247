from dataclasses import replace

from core import StructuredLogger, load_app_config, save_user_config_patch
from data import MT5DataGateway
from engine import ScannerEngine
from notifiers import TelegramNotifier
from services import AlertService, ScanService
from storage import SQLiteStore, StateManager
from strategy import StrategyEngine
from .runtime_state import RuntimeState
from .scanner_service import ScannerCommandService
from .symbol_registry import SymbolRegistry
from .telegram_bot import TelegramCommandBot

import scanner.config.htf as htf_runtime_config
import scanner.patterns.ob as ob_runtime


class AppController:
    def __init__(self):
        self.config = load_app_config()
        self._apply_ob_fvg_mode(self.config.scanner.ob_fvg_mode)
        self.logger = StructuredLogger()
        self.sqlite = SQLiteStore()
        self.state_manager = StateManager(self.sqlite)
        self.data_gateway = MT5DataGateway(self.logger)
        self.symbol_registry = SymbolRegistry(self.config.scanner.symbols, self.config.scanner.symbol_aliases)
        self.runtime_state = RuntimeState(self.symbol_registry.get_all_symbols())
        self.notifier = TelegramNotifier(self.config.telegram, self.logger)
        self.strategy = StrategyEngine(trigger_timeframes=self.config.scanner.ltf_timeframes)
        self.alert_service = AlertService(self.config, self.state_manager, self.notifier, self.logger)
        self.scan_service = ScanService(
            data_gateway=self.data_gateway,
            strategy_engine=self.strategy,
            state_manager=self.state_manager,
            alert_service=self.alert_service,
            logger=self.logger,
        )
        self.engine = ScannerEngine(
            config=self.config,
            data_gateway=self.data_gateway,
            notifier=self.notifier,
            state_manager=self.state_manager,
            scan_service=self.scan_service,
            logger=self.logger,
            runtime_state=self.runtime_state,
        )
        self.scanner_service = ScannerCommandService(
            engine=self.engine,
            symbol_registry=self.symbol_registry,
            runtime_state=self.runtime_state,
            logger=self.logger,
        )
        self.telegram_bot = TelegramCommandBot(
            config=self.config.telegram,
            notifier=self.notifier,
            symbol_registry=self.symbol_registry,
            scanner_service=self.scanner_service,
            logger=self.logger,
        )
        self.scanner_service.start()
        self.telegram_bot.start()
        self.logger.info(
            f"{self.config.app.name} v{self.config.app.version} started",
            phase="system",
            reason=f"strategy v{self.config.app.strategy_version}",
        )

    @staticmethod
    def _normalize_ob_fvg_mode(mode: str | None) -> str:
        value = str(mode or "medium").strip().lower()
        if value not in {"strict", "medium"}:
            raise ValueError("OB FVG mode must be 'strict' or 'medium'.")
        return value

    def _apply_ob_fvg_mode(self, mode: str) -> str:
        normalized = self._normalize_ob_fvg_mode(mode)
        htf_runtime_config.HTF_OB_FVG_MODE = normalized
        ob_runtime.HTF_OB_FVG_MODE = normalized
        return normalized

    def current_ob_fvg_mode(self) -> str:
        return self._normalize_ob_fvg_mode(getattr(ob_runtime, "HTF_OB_FVG_MODE", "medium"))

    def set_ob_fvg_mode(self, mode: str, persist: bool = True):
        try:
            normalized = self._apply_ob_fvg_mode(mode)
        except ValueError as exc:
            return False, str(exc)
        self.config = replace(
            self.config,
            scanner=replace(self.config.scanner, ob_fvg_mode=normalized),
        )
        if persist:
            save_user_config_patch({"scanner": {"ob_fvg_mode": normalized}})
        self.logger.info(
            "HTF OB FVG mode updated",
            phase="system",
            reason=f"mode={normalized}",
        )
        return True, f"HTF OB FVG mode set to {normalized}."

    def start(self, interval_sec: int | None = None):
        if interval_sec is not None:
            self.engine.set_interval(interval_sec)
        return self.engine.start()

    def stop(self):
        return self.engine.stop()

    def run_once(self):
        return self.engine.run_once()

    def set_interval(self, interval_sec: int):
        self.engine.set_interval(interval_sec)

    def rescan_now(self):
        return self.engine.rescan_now()

    def rescan_symbol(self, symbol: str):
        return self.engine.rescan_symbol(symbol)

    def clear_activity_log(self):
        self.logger.clear_recent_history()

    def shutdown(self):
        self.telegram_bot.stop()
        self.scanner_service.stop()
        self.engine.stop()

    def snapshot(self):
        snapshot = self.engine.snapshot()
        snapshot["strategy"] = {
            "ob_fvg_mode": self.current_ob_fvg_mode(),
        }
        snapshot["runtime"] = {
            "active_jobs": self.runtime_state.list_active_jobs(),
            "recent_jobs": self.runtime_state.recent_jobs(limit=10),
            "full_scan_active": self.runtime_state.is_full_scan_active(),
        }
        return snapshot
