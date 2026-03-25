"""UI-facing application facade.

Composition and lifecycle live in ``app.composition`` and ``app.lifecycle``.
"""

from infra.config import load_app_config

from .lifecycle import AppLifecycle


class AppController:
    def __init__(self):
        self.config = load_app_config()
        self.lifecycle = AppLifecycle(self.config)
        self._sync_runtime_handles()

    @staticmethod
    def _normalize_ob_fvg_mode(mode: str | None) -> str:
        return AppLifecycle.normalize_ob_fvg_mode(mode)

    def current_ob_fvg_mode(self) -> str:
        return self.lifecycle.current_ob_fvg_mode()

    def _sync_runtime_handles(self) -> None:
        runtime = self.lifecycle.runtime
        self.config = self.lifecycle.config
        self.logger = runtime.logger
        self.sqlite = runtime.sqlite
        self.state_manager = runtime.state_manager
        self.data_gateway = runtime.data_gateway
        self.symbol_registry = runtime.symbol_registry
        self.runtime_state = runtime.runtime_state
        self.notifier = runtime.notifier
        self.strategy = runtime.strategy
        self.alert_service = runtime.alert_service
        self.scan_service = runtime.scan_service
        self.engine = runtime.engine
        self.scanner_service = runtime.scanner_service
        self.telegram_bot = runtime.telegram_bot

    def set_ob_fvg_mode(self, mode: str, persist: bool = True):
        ok, message = self.lifecycle.set_ob_fvg_mode(mode, persist=persist)
        self._sync_runtime_handles()
        return ok, message

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
        self.lifecycle.shutdown()

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
