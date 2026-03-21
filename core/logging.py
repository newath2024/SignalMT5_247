import datetime as dt
import logging
import threading
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import LOGS_DIR, ensure_runtime_layout


WATCH_LEVEL = 25
SIGNAL_LEVEL = 35
logging.addLevelName(WATCH_LEVEL, "WATCH")
logging.addLevelName(SIGNAL_LEVEL, "SIGNAL")


class StructuredLogger:
    def __init__(self, log_dir: Path | None = None, history_limit: int = 500):
        ensure_runtime_layout()
        self._history = deque(maxlen=history_limit)
        self._lock = threading.RLock()
        self.log_dir = Path(log_dir or LOGS_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "app.log"

        self._logger = logging.getLogger("openclaw.desktop")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            formatter = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def _entry(self, level: str, message: str, symbol: str | None, timeframe: str | None, phase: str | None, reason: str | None):
        timestamp = dt.datetime.now()
        return {
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "label": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "symbol": symbol or "-",
            "timeframe": timeframe or "-",
            "phase": phase or "-",
            "reason": reason or "",
            "message": str(message),
        }

    @staticmethod
    def _format(entry: dict[str, str]) -> str:
        base = f"[{entry['level']}] {entry['symbol']} {entry['timeframe']} {entry['message']}"
        details = []
        if entry["phase"] and entry["phase"] != "-":
            details.append(f"phase={entry['phase']}")
        if entry["reason"]:
            details.append(f"reason={entry['reason']}")
        if not details:
            return base
        return f"{base} | {' | '.join(details)}"

    def _log(self, numeric_level: int, level_name: str, message: str, symbol: str | None = None, timeframe: str | None = None, phase: str | None = None, reason: str | None = None):
        entry = self._entry(level_name, message, symbol, timeframe, phase, reason)
        with self._lock:
            self._history.append(entry)
        self._logger.log(numeric_level, self._format(entry))

    def info(self, message: str, symbol: str | None = None, timeframe: str | None = None, phase: str | None = None, reason: str | None = None):
        self._log(logging.INFO, "INFO", message, symbol, timeframe, phase, reason)

    def watch(self, message: str, symbol: str | None = None, timeframe: str | None = None, phase: str | None = None, reason: str | None = None):
        self._log(WATCH_LEVEL, "WATCH", message, symbol, timeframe, phase, reason)

    def signal(self, message: str, symbol: str | None = None, timeframe: str | None = None, phase: str | None = None, reason: str | None = None):
        self._log(SIGNAL_LEVEL, "SIGNAL", message, symbol, timeframe, phase, reason)

    def warn(self, message: str, symbol: str | None = None, timeframe: str | None = None, phase: str | None = None, reason: str | None = None):
        self._log(logging.WARNING, "WARN", message, symbol, timeframe, phase, reason)

    def error(self, message: str, symbol: str | None = None, timeframe: str | None = None, phase: str | None = None, reason: str | None = None):
        self._log(logging.ERROR, "ERROR", message, symbol, timeframe, phase, reason)

    def recent_entries(self, limit: int = 200) -> list[dict[str, str]]:
        with self._lock:
            history = list(self._history)
        if limit >= len(history):
            return history
        return history[-limit:]

    def clear_recent_history(self):
        with self._lock:
            self._history.clear()
