from scanner.data.market_data_service import build_symbol_snapshot
from scanner.deps import mt5


class MT5DataGateway:
    def __init__(self, logger):
        self.logger = logger
        self._connected = False
        self._terminal_name = "Disconnected"
        self._last_error = None

    def connect(self) -> bool:
        try:
            if not mt5.initialize():
                error_code, error_message = mt5.last_error()
                raise RuntimeError(f"MT5 initialize() failed: [{error_code}] {error_message}")
            terminal_info = mt5.terminal_info()
            self._connected = True
            self._terminal_name = terminal_info.name if terminal_info else "MetaTrader 5"
            self._last_error = None
            self.logger.info(
                f"Connected to MT5: {self._terminal_name}",
                phase="connection",
            )
            return True
        except Exception as exc:
            self._connected = False
            self._last_error = str(exc)
            self.logger.error(
                "MT5 connection failed",
                phase="connection",
                reason=str(exc),
            )
            return False

    def ensure_connected(self) -> bool:
        if self._connected:
            return True
        return self.connect()

    def disconnect(self):
        if self._connected:
            mt5.shutdown()
        self._connected = False
        self._terminal_name = "Disconnected"

    def fetch_symbol_snapshot(self, symbol: str):
        if not self.ensure_connected():
            return None
        try:
            snapshot = build_symbol_snapshot(symbol)
            if snapshot is None:
                self._last_error = f"Market data unavailable for {symbol}"
            else:
                self._last_error = None
            return snapshot
        except Exception as exc:
            self._last_error = str(exc)
            self.logger.error(
                "MT5 snapshot fetch failed",
                symbol=symbol,
                phase="connection",
                reason=str(exc),
            )
            return None

    def status_snapshot(self) -> dict:
        return {
            "connected": self._connected,
            "terminal_name": self._terminal_name,
            "last_error": self._last_error,
        }
