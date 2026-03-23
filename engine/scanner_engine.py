import threading
import time
import os

from core.enums import SetupPhase, SetupState
from strategy.reason_engine import describe_error


class ScannerEngine:
    def __init__(self, config, data_gateway, notifier, state_manager, scan_service, logger, runtime_state=None):
        self.config = config
        self.data_gateway = data_gateway
        self.notifier = notifier
        self.state_manager = state_manager
        self.scan_service = scan_service
        self.logger = logger
        self.runtime_state = runtime_state

        self._lock = threading.RLock()
        self._scan_lock = threading.RLock()
        self._thread = None
        self._stop_event = None
        self._status = "idle"
        self._started_at = None
        self._last_cycle = None
        self._last_error = None
        self._interval_sec = config.scanner.loop_interval_sec
        self._mt5_retry_delay_sec = max(5, int(os.getenv("OPENCLAW_MT5_RECONNECT_DELAY_SEC", "10")))
        self._cycle_progress = self._empty_cycle_progress()
        persisted = {
            item["symbol"]: item
            for item in self.state_manager.list_symbol_states(config.scanner.symbols)
        }
        self._symbol_states = {
            symbol: self._hydrate_symbol_state(symbol, persisted.get(symbol))
            for symbol in config.scanner.symbols
        }
        if self.runtime_state is not None:
            self.runtime_state.seed_symbol_states(list(self._symbol_states.values()))

    @staticmethod
    def _empty_cycle_progress() -> dict:
        return {
            "active": False,
            "current": 0,
            "completed": 0,
            "total": 0,
            "current_symbol": None,
            "started_at": None,
            "finished_at": None,
            "updated_at": None,
        }

    @staticmethod
    def _normalize_phase(value: str | None) -> str:
        mapping = {
            None: SetupPhase.HTF_CONTEXT.value,
            "htf scan": SetupPhase.HTF_CONTEXT.value,
            "ltf confirmation": SetupPhase.LTF_SWEEP.value,
            "watch armed": SetupPhase.IFVG_VALIDATION.value,
            "mss confirmation": SetupPhase.WAITING_MSS.value,
            "signal confirmation": SetupPhase.READY.value,
            "cooldown": SetupPhase.ALERT_SENT.value,
            "deduplication": SetupPhase.ALERT_SENT.value,
            "alert delivery": SetupPhase.ALERT_SENT.value,
            "alert configuration": SetupPhase.ALERT_SENT.value,
            "connection": SetupPhase.HTF_CONTEXT.value,
            "system": SetupPhase.HTF_CONTEXT.value,
        }
        return mapping.get(value, value or SetupPhase.HTF_CONTEXT.value)

    def _default_symbol_state(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "state": SetupState.IDLE.value,
            "bias": "neutral",
            "tf": "-",
            "phase": SetupPhase.HTF_CONTEXT.value,
            "reason": "waiting: HTF context",
            "price": None,
            "score": None,
            "grade": None,
            "last_update": None,
            "scanned_at": None,
            "cooldown_remaining": 0,
            "cooldown_duration_sec": self.config.scanner.cooldown_sec,
            "cooldown_until": None,
            "last_alert_time": None,
            "active_watch_id": None,
            "htf_context": "-",
            "transition": None,
            "detail": {
                "current_state": SetupState.IDLE.value,
                "htf_bias": "neutral",
                "htf_context": "-",
                "htf_context_reason": "Awaiting first scan cycle",
                "last_detected_sweep": "-",
                "last_detected_mss": "-",
                "last_detected_ifvg": "-",
                "rejection_reason": "-",
                "last_alert_time": None,
                "cooldown_info": "-",
                "active_watch_id": None,
                "active_watch_info": "-",
                "zone": "-",
                "zone_top_bottom": "-",
                "score": "-",
                "last_alert_details": "-",
                "timeline": "-",
            },
        }

    def _hydrate_symbol_state(self, symbol: str, persisted: dict | None) -> dict:
        state = self._default_symbol_state(symbol)
        if not persisted:
            return state
        hydrated = dict(state)
        hydrated.update(persisted)
        hydrated["phase"] = self._normalize_phase(hydrated.get("phase"))
        detail = dict(state["detail"])
        detail.update(hydrated.get("detail") or {})
        detail.setdefault("phase", hydrated["phase"])
        detail.setdefault("score", "-")
        detail.setdefault("last_alert_details", "-")
        detail.setdefault("active_watch_info", "-")
        detail.setdefault("zone_top_bottom", detail.get("zone", "-"))
        detail.setdefault("timeline", "-")
        hydrated["detail"] = detail
        hydrated.setdefault("score", None)
        hydrated.setdefault("grade", None)
        hydrated.setdefault("cooldown_duration_sec", self.config.scanner.cooldown_sec)
        return hydrated

    def set_interval(self, interval_sec: int):
        with self._lock:
            self._interval_sec = max(5, int(interval_sec))

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False, "Scanner already running."
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._runner, name="OpenClawScannerEngine", daemon=True)
            self._status = "starting"
            self._started_at = time.time()
            self._last_error = None
            self._cycle_progress = self._empty_cycle_progress()
            self._thread.start()
        return True, "Scanner started."

    def stop(self):
        thread = None
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._status = "stopped"
                self._cycle_progress = self._empty_cycle_progress()
                return False, "Scanner is not running."
            self._status = "stopping"
            self._stop_event.set()
            thread = self._thread

        thread.join(timeout=3.0)
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._status = "stopped"
                self._cycle_progress = self._empty_cycle_progress()
        return True, "Scanner stopping."

    def _scan_symbol(self, symbol: str) -> dict:
        try:
            return self.scan_service.scan_symbol(symbol)
        except Exception as exc:
            self.logger.error("Symbol scan failed", symbol=symbol, phase="system", reason=str(exc))
            return {
                "symbol": symbol,
                "state": SetupState.ERROR.value,
                "bias": "neutral",
                "tf": "-",
                "phase": SetupPhase.HTF_CONTEXT.value,
                "reason": describe_error(str(exc)),
                "price": None,
                "score": None,
                "grade": None,
                "last_update": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "scanned_at": time.time(),
                "cooldown_remaining": 0,
                "cooldown_duration_sec": self.config.scanner.cooldown_sec,
                "cooldown_until": None,
                "last_alert_time": None,
                "active_watch_id": None,
                "htf_context": "-",
                "transition": None,
                "detail": {
                    "current_state": SetupState.ERROR.value,
                    "htf_bias": "neutral",
                    "htf_context": "-",
                    "htf_context_reason": "Symbol scan failed",
                    "last_detected_sweep": "-",
                    "last_detected_mss": "-",
                    "last_detected_ifvg": "-",
                    "rejection_reason": "-",
                    "last_alert_time": None,
                    "cooldown_info": "-",
                    "active_watch_id": None,
                    "active_watch_info": "-",
                    "zone": "-",
                    "zone_top_bottom": "-",
                    "score": "-",
                    "last_alert_details": "-",
                    "timeline": "-",
                },
            }

    def _store_symbol_result(self, result: dict):
        with self._lock:
            self._symbol_states[result["symbol"]] = dict(result)
        if self.runtime_state is not None:
            self.runtime_state.update_symbol_state(result)

    def _set_cycle_progress(
        self,
        *,
        active: bool,
        total: int,
        current: int = 0,
        completed: int = 0,
        current_symbol: str | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
    ):
        now = time.time()
        with self._lock:
            progress = dict(self._cycle_progress)
            progress.update(
                {
                    "active": active,
                    "total": max(0, int(total)),
                    "current": max(0, int(current)),
                    "completed": max(0, int(completed)),
                    "current_symbol": current_symbol,
                    "started_at": started_at if started_at is not None else progress.get("started_at"),
                    "finished_at": finished_at,
                    "updated_at": now,
                }
            )
            self._cycle_progress = progress

    def run_once(self):
        if not self.data_gateway.ensure_connected():
            return []
        return self._run_cycle()

    def rescan_now(self):
        if not self.data_gateway.ensure_connected():
            return []
        self.logger.info("Manual rescan requested", phase="system", reason="operator action")
        return self._run_cycle()

    def rescan_symbol(self, symbol: str):
        if symbol not in self.config.scanner.symbols:
            raise ValueError(f"Unknown symbol: {symbol}")
        if not self.data_gateway.ensure_connected():
            return None
        self.logger.info("Manual symbol rescan requested", symbol=symbol, phase="system", reason="operator action")
        scan_started_at = time.time()
        self._set_cycle_progress(
            active=True,
            total=1,
            current=1,
            completed=0,
            current_symbol=symbol,
            started_at=scan_started_at,
        )
        with self._lock:
            self._status = "scanning"
        with self._scan_lock:
            result = self._scan_symbol(symbol)
        self._store_symbol_result(result)
        scan_finished_at = time.time()
        self._set_cycle_progress(
            active=False,
            total=1,
            current=1,
            completed=1,
            current_symbol=None,
            started_at=scan_started_at,
            finished_at=scan_finished_at,
        )
        with self._lock:
            self._last_cycle = {
                "started_at": scan_started_at,
                "finished_at": scan_finished_at,
                "duration_sec": max(0.0, scan_finished_at - scan_started_at),
                "symbol_count": 1,
                "alerts_today": self.state_manager.confirmed_signals_today(),
            }
            self._status = "running" if self._thread is not None and self._thread.is_alive() else "idle"
        return result

    def _run_cycle(self):
        results = []
        cycle_started_at = time.time()
        total_symbols = len(self.config.scanner.symbols)
        self._set_cycle_progress(
            active=True,
            total=total_symbols,
            current=0,
            completed=0,
            current_symbol=None,
            started_at=cycle_started_at,
        )
        with self._lock:
            self._status = "scanning"
        with self._scan_lock:
            for index, symbol in enumerate(self.config.scanner.symbols, start=1):
                self._set_cycle_progress(
                    active=True,
                    total=total_symbols,
                    current=index,
                    completed=index - 1,
                    current_symbol=symbol,
                    started_at=cycle_started_at,
                )
                result = self._scan_symbol(symbol)
                results.append(result)
                self._store_symbol_result(result)
                self._set_cycle_progress(
                    active=True,
                    total=total_symbols,
                    current=index,
                    completed=index,
                    current_symbol=symbol,
                    started_at=cycle_started_at,
                )

        cycle_finished_at = time.time()
        summary = {
            "started_at": cycle_started_at,
            "finished_at": cycle_finished_at,
            "duration_sec": max(0.0, cycle_finished_at - cycle_started_at),
            "symbol_count": len(results),
            "alerts_today": self.state_manager.confirmed_signals_today(),
        }
        self._set_cycle_progress(
            active=False,
            total=total_symbols,
            current=total_symbols,
            completed=len(results),
            current_symbol=None,
            started_at=cycle_started_at,
            finished_at=cycle_finished_at,
        )
        with self._lock:
            self._last_cycle = summary
            self._status = "running" if self._thread is not None and self._thread.is_alive() else "idle"
        return results

    def _runner(self):
        try:
            while not self._stop_event.is_set():
                if not self.data_gateway.ensure_connected():
                    with self._lock:
                        self._status = "waiting_mt5"
                        self._last_error = self.data_gateway.status_snapshot().get("last_error")
                    self.logger.warn(
                        "MT5 not ready; scanner will retry automatically",
                        phase="connection",
                        reason=self._last_error or "waiting for MT5",
                    )
                    if self._stop_event.wait(self._mt5_retry_delay_sec):
                        break
                    continue

                self._run_cycle()
                if self._stop_event.wait(self._interval_sec):
                    break
        except Exception as exc:
            with self._lock:
                self._status = "error"
                self._last_error = str(exc)
            self.logger.error("Scanner engine crashed", phase="system", reason=str(exc))
        finally:
            self.data_gateway.disconnect()
            with self._lock:
                self._thread = None
                if self._status != "error":
                    self._cycle_progress = self._empty_cycle_progress()
                if self._status not in ("error", "stopped"):
                    self._status = "idle"

    def snapshot(self) -> dict:
        with self._lock:
            thread_running = self._thread is not None and self._thread.is_alive()
            progress = dict(self._cycle_progress)
            running = thread_running or bool(progress.get("active"))
            next_scan_at = None
            if thread_running and self._last_cycle and not progress.get("active"):
                next_scan_at = self._last_cycle["finished_at"] + self._interval_sec
            scanner = {
                "running": running,
                "status": self._status,
                "interval_sec": self._interval_sec,
                "started_at": self._started_at,
                "last_cycle": dict(self._last_cycle) if self._last_cycle else None,
                "last_error": self._last_error,
                "next_scan_at": next_scan_at,
                "progress": progress,
            }
            symbols = [dict(self._symbol_states[symbol]) for symbol in self.config.scanner.symbols]

        watches = self.state_manager.list_active_watches(statuses=("armed", "waiting_mss"))
        alerts = self.state_manager.recent_alerts(limit=50)
        logs = self.logger.recent_entries(limit=200)

        return {
            "app": self.config.app,
            "scanner": scanner,
            "connections": {
                "mt5": self.data_gateway.status_snapshot(),
                "telegram": self.notifier.status_snapshot(),
            },
            "metrics": {
                "active_watches": sum(1 for item in watches if item.get("status") in {"armed", "waiting_mss"}),
                "confirmed_signals_today": self.state_manager.confirmed_signals_today(),
                "total_symbols": len(self.config.scanner.symbols),
                "scanned_symbols": sum(1 for item in symbols if item.get("scanned_at")),
            },
            "symbols": symbols,
            "watches": watches,
            "alerts": alerts,
            "logs": logs,
            "rejections": self.state_manager.recent_rejections(limit=20),
        }
