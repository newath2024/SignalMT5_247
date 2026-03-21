from dataclasses import replace

from core import StructuredLogger, load_app_config, save_user_config_patch
from data import MT5DataGateway
from engine import ScannerEngine
from notifiers import TelegramNotifier
from services import AlertService, ScanService
from storage import SQLiteStore, StateManager
from strategy import StrategyEngine

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
        )
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

    def snapshot(self):
        snapshot = self.engine.snapshot()
        snapshot["strategy"] = {
            "ob_fvg_mode": self.current_ob_fvg_mode(),
        }
        return snapshot
