"""UI-facing application facade.

Composition and lifecycle live in ``app.composition`` and ``app.lifecycle``.
"""

from .lifecycle import AppLifecycle


class AppController:
    def __init__(self, lifecycle: AppLifecycle):
        self.lifecycle = lifecycle

    @staticmethod
    def _normalize_ob_fvg_mode(mode: str | None) -> str:
        return AppLifecycle.normalize_ob_fvg_mode(mode)

    def current_ob_fvg_mode(self) -> str:
        return self.lifecycle.current_ob_fvg_mode()

    @property
    def config(self):
        return self.lifecycle.config

    @property
    def logger(self):
        return self.lifecycle.runtime.logger

    @property
    def runtime_state(self):
        return self.lifecycle.runtime.runtime_state

    @property
    def engine(self):
        return self.lifecycle.runtime.engine

    def set_ob_fvg_mode(self, mode: str, persist: bool = True):
        return self.lifecycle.set_ob_fvg_mode(mode, persist=persist)

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
