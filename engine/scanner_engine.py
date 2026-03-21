import threading
import time


class ScannerEngine:
    def __init__(self, config, data_gateway, notifier, state_manager, scan_service, logger):
        self.config = config
        self.data_gateway = data_gateway
        self.notifier = notifier
        self.state_manager = state_manager
        self.scan_service = scan_service
        self.logger = logger

        self._lock = threading.RLock()
        self._thread = None
        self._stop_event = None
        self._status = "idle"
        self._started_at = None
        self._last_cycle = None
        self._last_error = None
        self._interval_sec = config.scanner.loop_interval_sec
        self._symbol_states = {
            symbol: {
                "symbol": symbol,
                "status": "idle",
                "message": "Awaiting first scan cycle",
                "scanned_at": None,
                "current_price": None,
                "timeframe": "-",
                "bias": "-",
                "last_rejection": None,
            }
            for symbol in config.scanner.symbols
        }

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
            self._thread.start()
        return True, "Scanner started."

    def stop(self):
        thread = None
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._status = "stopped"
                return False, "Scanner is not running."
            self._status = "stopping"
            self._stop_event.set()
            thread = self._thread

        thread.join(timeout=3.0)
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._status = "stopped"
        return True, "Scanner stopping."

    def run_once(self):
        if not self.data_gateway.ensure_connected():
            return []
        return self._run_cycle()

    def _run_cycle(self):
        results = []
        cycle_started_at = time.time()
        for symbol in self.config.scanner.symbols:
            try:
                result = self.scan_service.scan_symbol(symbol)
            except Exception as exc:
                self.logger.error("Symbol scan failed", symbol=symbol, phase="system", reason=str(exc))
                result = {
                    "symbol": symbol,
                    "status": "error",
                    "message": str(exc),
                    "scanned_at": time.time(),
                    "current_price": None,
                    "timeframe": "-",
                    "bias": "-",
                    "last_rejection": self.state_manager.last_rejection_for_symbol(symbol),
                }
            results.append(result)
            with self._lock:
                self._symbol_states[symbol] = dict(result)

        cycle_finished_at = time.time()
        summary = {
            "started_at": cycle_started_at,
            "finished_at": cycle_finished_at,
            "duration_sec": max(0.0, cycle_finished_at - cycle_started_at),
            "symbol_count": len(results),
            "alerts_today": self.state_manager.confirmed_signals_today(),
        }
        with self._lock:
            self._last_cycle = summary
            self._status = "running"
        return results

    def _runner(self):
        try:
            if not self.data_gateway.ensure_connected():
                with self._lock:
                    self._status = "error"
                    self._last_error = self.data_gateway.status_snapshot().get("last_error")
                return

            while not self._stop_event.is_set():
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
                if self._status not in ("error", "stopped"):
                    self._status = "idle"

    def snapshot(self) -> dict:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            scanner = {
                "running": running,
                "status": self._status,
                "interval_sec": self._interval_sec,
                "started_at": self._started_at,
                "last_cycle": dict(self._last_cycle) if self._last_cycle else None,
                "last_error": self._last_error,
            }
            symbols = [dict(self._symbol_states[symbol]) for symbol in self.config.scanner.symbols]

        watches = self.state_manager.list_active_watches(statuses=("armed", "confirmed", "cooldown"))
        alerts = self.state_manager.recent_alerts(limit=20)
        logs = self.logger.recent_entries(limit=100)

        return {
            "app": self.config.app,
            "scanner": scanner,
            "connections": {
                "mt5": self.data_gateway.status_snapshot(),
                "telegram": self.notifier.status_snapshot(),
            },
            "metrics": {
                "active_watches": sum(1 for item in watches if item.get("status") == "armed"),
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
