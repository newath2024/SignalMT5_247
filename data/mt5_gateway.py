from scanner.data.market_data_service import build_symbol_snapshot
from scanner.deps import mt5
from core.mt5_runtime import check_mt5_session, connect_mt5_with_retry, load_mt5_runtime_settings


class MT5DataGateway:
    def __init__(self, logger):
        self.logger = logger
        self._connected = False
        self._terminal_name = "Disconnected"
        self._last_error = None
        self._session_state = "disconnected"
        self._settings = load_mt5_runtime_settings()
        self._last_status_key = None

    def _log_status(self, level: str, message: str, *, reason: str | None = None):
        status_key = (level, message, reason)
        if status_key == self._last_status_key:
            return
        self._last_status_key = status_key
        handler = getattr(self.logger, level, self.logger.info)
        handler(message, phase="connection", reason=reason)

    def connect(self, probe_symbol: str | None = None) -> bool:
        try:
            report = connect_mt5_with_retry(mt5, symbol=probe_symbol, settings=self._settings, logger=self.logger)
        except Exception as exc:
            self._connected = False
            self._session_state = "initialize_failed"
            self._last_error = str(exc)
            self._log_status("error", "MT5 connection failed", reason=str(exc))
            return False

        self._connected = report.ready
        self._terminal_name = report.terminal_name or "MetaTrader 5"
        self._session_state = report.state
        self._last_error = None if report.ready else report.message
        if report.ready:
            self._log_status("info", f"Connected to MT5: {self._terminal_name}")
            return True

        log_level = "warn" if report.state in {"no_saved_session", "tick_unavailable", "tick_stale"} else "error"
        self._log_status(log_level, "MT5 is not ready yet", reason=report.message)
        return False

    def ensure_connected(self, probe_symbol: str | None = None) -> bool:
        if self._connected:
            report = check_mt5_session(mt5, symbol=probe_symbol, settings=self._settings)
            if report.ready:
                self._terminal_name = report.terminal_name or self._terminal_name
                self._last_error = None
                self._session_state = report.state
                return True
            self._connected = False
            self._session_state = report.state
            self._last_error = report.message
            self._log_status("warn", "MT5 session check failed", reason=report.message)
        return self.connect(probe_symbol=probe_symbol)

    def disconnect(self):
        if self._connected:
            mt5.shutdown()
        self._connected = False
        self._terminal_name = "Disconnected"
        self._session_state = "disconnected"

    def fetch_symbol_snapshot(self, symbol: str):
        if not self.ensure_connected(probe_symbol=symbol):
            return None
        attempts = 2
        for attempt in range(1, attempts + 1):
            try:
                snapshot = build_symbol_snapshot(symbol)
                if snapshot is not None:
                    self._last_error = None
                    self._session_state = "ready"
                    self._connected = True
                    return snapshot

                report = check_mt5_session(mt5, symbol=symbol, settings=self._settings)
                self._connected = report.ready
                self._session_state = report.state
                self._last_error = report.message if not report.ready else f"Market data unavailable for {symbol}"
                if attempt < attempts and not report.ready:
                    self._log_status(
                        "warn",
                        "MT5 snapshot fetch lost readiness, reconnecting",
                        reason=f"symbol={symbol} detail={report.message}",
                    )
                    self.disconnect()
                    if self.ensure_connected(probe_symbol=symbol):
                        continue
                return None
            except Exception as exc:
                self._last_error = str(exc)
                self._connected = False
                self._session_state = "fetch_failed"
                self.logger.error(
                    "MT5 snapshot fetch failed",
                    symbol=symbol,
                    phase="connection",
                    reason=str(exc),
                )
                if attempt < attempts and self.ensure_connected(probe_symbol=symbol):
                    continue
                return None

    def status_snapshot(self) -> dict:
        return {
            "connected": self._connected,
            "terminal_name": self._terminal_name,
            "last_error": self._last_error,
            "session_state": self._session_state,
            "terminal_path": str(self._settings.terminal_path) if self._settings.terminal_path else None,
        }
