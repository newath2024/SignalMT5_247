from __future__ import annotations

import ctypes
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from infra.config.paths import PROJECT_ROOT


SW_HIDE = 0
SW_MINIMIZE = 6


@dataclass(frozen=True)
class MT5RuntimeSettings:
    terminal_path: Path | None
    portable_root: Path
    start_timeout_sec: int
    init_retries: int
    init_retry_delay_sec: float
    launch_delay_sec: float
    auto_launch: bool
    init_mode: str
    require_saved_session: bool
    max_tick_age_sec: int
    window_mode: str
    ready_symbol: str | None


@dataclass(frozen=True)
class MT5SessionReport:
    ready: bool
    state: str
    message: str
    terminal_path: Path | None = None
    terminal_name: str | None = None
    account_login: int | None = None
    account_server: str | None = None
    symbol: str | None = None
    tick_time: int | None = None
    tick_age_sec: float | None = None
    last_error: tuple[int, str] | None = None


MT5RuntimeReport = MT5SessionReport


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = str(raw_value).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return max(minimum, int(str(raw_value).strip()))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return max(minimum, float(str(raw_value).strip()))
    except (TypeError, ValueError):
        return default


def _resolve_path(raw_path: str | None, root: Path) -> Path | None:
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _coerce_symbol(symbol: str | None) -> str | None:
    value = str(symbol or "").strip().upper()
    return value or None


def _emit(logger: Any, level: str, message: str, **kwargs):
    if logger is None:
        return
    handler = getattr(logger, level, None)
    if callable(handler):
        try:
            handler(message, **kwargs)
            return
        except TypeError:
            handler(message)
            return
    if callable(logger):
        logger(message)


def _session_message(state: str, message: str, **kwargs) -> MT5SessionReport:
    return MT5SessionReport(
        ready=state == "ready",
        state=state,
        message=message,
        **kwargs,
    )


def load_mt5_runtime_settings() -> MT5RuntimeSettings:
    portable_root = Path(os.getenv("OPENCLAW_PORTABLE_ROOT") or PROJECT_ROOT).expanduser().resolve()
    terminal_path = _resolve_path(
        os.getenv("OPENCLAW_MT5_TERMINAL"),
        portable_root,
    )
    if terminal_path is None:
        terminal_path = (portable_root / "mt5_portable" / "terminal64.exe").resolve()

    window_mode = str(os.getenv("OPENCLAW_MT5_WINDOW_MODE", "normal")).strip().lower()
    if window_mode not in {"normal", "minimize", "hide"}:
        window_mode = "normal"

    init_mode = str(os.getenv("OPENCLAW_MT5_INIT_MODE", "auto")).strip().lower()
    if init_mode not in {"auto", "path", "attach"}:
        init_mode = "auto"

    return MT5RuntimeSettings(
        terminal_path=terminal_path,
        portable_root=portable_root,
        start_timeout_sec=_env_int("OPENCLAW_MT5_START_TIMEOUT_SEC", 90, minimum=10),
        init_retries=_env_int("OPENCLAW_MT5_INIT_RETRIES", 12, minimum=1),
        init_retry_delay_sec=_env_float("OPENCLAW_MT5_INIT_RETRY_DELAY_SEC", 3.0, minimum=0.5),
        launch_delay_sec=_env_float("OPENCLAW_MT5_LAUNCH_DELAY_SEC", 1.0, minimum=0.0),
        auto_launch=_env_flag("OPENCLAW_MT5_AUTO_LAUNCH", True),
        init_mode=init_mode,
        require_saved_session=_env_flag("OPENCLAW_MT5_REQUIRE_SAVED_SESSION", True),
        max_tick_age_sec=_env_int("OPENCLAW_MT5_TICK_MAX_AGE_SEC", 0, minimum=0),
        window_mode=window_mode,
        ready_symbol=_coerce_symbol(os.getenv("OPENCLAW_MT5_READY_SYMBOL")),
    )


def resolve_probe_symbol(explicit_symbol: str | None = None) -> str | None:
    symbol = _coerce_symbol(explicit_symbol)
    if symbol:
        return symbol
    settings = load_mt5_runtime_settings()
    return settings.ready_symbol


def launch_mt5_terminal(settings: MT5RuntimeSettings | None = None, logger: Any = None) -> subprocess.Popen | None:
    settings = settings or load_mt5_runtime_settings()
    terminal_path = settings.terminal_path
    if not settings.auto_launch:
        _emit(logger, "info", "MT5 auto-launch disabled by environment.")
        return None
    if terminal_path is None:
        raise FileNotFoundError("MT5 terminal path is not configured.")
    if not terminal_path.exists():
        raise FileNotFoundError(f"Portable MT5 terminal was not found at {terminal_path}")

    _emit(
        logger,
        "info",
        "Launching portable MT5 terminal",
        phase="connection",
        reason=f"path={terminal_path}",
    )
    process = subprocess.Popen(
        [str(terminal_path), "/portable"],
        cwd=str(terminal_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    if settings.launch_delay_sec > 0:
        time.sleep(settings.launch_delay_sec)
    return process


def _find_window_handles_for_pid(process_id: int) -> list[int]:
    if process_id <= 0:
        return []

    user32 = ctypes.windll.user32
    handles: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) == int(process_id) and user32.IsWindowVisible(hwnd):
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return handles


def apply_mt5_window_mode(process_id: int | None, settings: MT5RuntimeSettings | None = None, logger: Any = None) -> bool:
    settings = settings or load_mt5_runtime_settings()
    if not process_id or settings.window_mode == "normal":
        return False

    handles = _find_window_handles_for_pid(int(process_id))
    if not handles:
        _emit(
            logger,
            "warn",
            "MT5 window mode requested but no window handle was found.",
            phase="connection",
            reason=f"mode={settings.window_mode}",
        )
        return False

    action = SW_MINIMIZE if settings.window_mode == "minimize" else SW_HIDE
    for hwnd in handles:
        ctypes.windll.user32.ShowWindow(hwnd, action)

    if settings.window_mode == "hide":
        _emit(
            logger,
            "warn",
            "MT5 window hide mode is enabled. This is less safe than minimize mode on Windows.",
            phase="connection",
            reason="mode=hide",
        )
    else:
        _emit(
            logger,
            "info",
            "Applied MT5 window mode",
            phase="connection",
            reason=f"mode={settings.window_mode}",
        )
    return True


def check_mt5_session(mt5, symbol: str | None = None, settings: MT5RuntimeSettings | None = None) -> MT5SessionReport:
    settings = settings or load_mt5_runtime_settings()
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        error = mt5.last_error()
        return _session_message(
            "terminal_unavailable",
            f"MT5 terminal is not connected yet: [{error[0]}] {error[1]}",
            terminal_path=settings.terminal_path,
            last_error=error,
        )

    terminal_name = getattr(terminal_info, "name", None) or "MetaTrader 5"
    account_info = mt5.account_info()
    account_login = getattr(account_info, "login", None) if account_info else None
    account_server = getattr(account_info, "server", None) if account_info else None

    if settings.require_saved_session and not account_login:
        return _session_message(
            "no_saved_session",
            "MT5 terminal launched but no active saved session was detected. Open MT5 once, login manually, and tick Save password.",
            terminal_path=settings.terminal_path,
            terminal_name=terminal_name,
        )

    probe_symbol = _coerce_symbol(symbol) or settings.ready_symbol
    if not probe_symbol:
        return _session_message(
            "ready",
            f"MT5 terminal is ready: {terminal_name}",
            terminal_path=settings.terminal_path,
            terminal_name=terminal_name,
            account_login=account_login,
            account_server=account_server,
        )

    info = mt5.symbol_info(probe_symbol)
    if info is None:
        return _session_message(
            "symbol_missing",
            f"MT5 terminal is logged in, but symbol {probe_symbol} was not found in this terminal.",
            terminal_path=settings.terminal_path,
            terminal_name=terminal_name,
            account_login=account_login,
            account_server=account_server,
            symbol=probe_symbol,
        )

    if not info.visible and not mt5.symbol_select(probe_symbol, True):
        return _session_message(
            "symbol_unavailable",
            f"MT5 terminal is logged in, but symbol {probe_symbol} could not be enabled in Market Watch.",
            terminal_path=settings.terminal_path,
            terminal_name=terminal_name,
            account_login=account_login,
            account_server=account_server,
            symbol=probe_symbol,
        )

    tick = mt5.symbol_info_tick(probe_symbol)
    if tick is None or not getattr(tick, "time", 0):
        return _session_message(
            "tick_unavailable",
            f"MT5 terminal is logged in, but no tick data is available yet for {probe_symbol}.",
            terminal_path=settings.terminal_path,
            terminal_name=terminal_name,
            account_login=account_login,
            account_server=account_server,
            symbol=probe_symbol,
        )

    tick_age_sec = max(0.0, time.time() - float(tick.time))
    if settings.max_tick_age_sec > 0 and tick_age_sec > settings.max_tick_age_sec:
        return _session_message(
            "tick_stale",
            f"MT5 terminal is logged in, but tick data for {probe_symbol} is stale ({tick_age_sec:.0f}s old).",
            terminal_path=settings.terminal_path,
            terminal_name=terminal_name,
            account_login=account_login,
            account_server=account_server,
            symbol=probe_symbol,
            tick_time=int(tick.time),
            tick_age_sec=tick_age_sec,
        )

    return _session_message(
        "ready",
        f"MT5 terminal is ready and {probe_symbol} has live symbol data.",
        terminal_path=settings.terminal_path,
        terminal_name=terminal_name,
        account_login=account_login,
        account_server=account_server,
        symbol=probe_symbol,
        tick_time=int(tick.time),
        tick_age_sec=tick_age_sec,
    )


def connect_mt5_with_retry(mt5, symbol: str | None = None, settings: MT5RuntimeSettings | None = None, logger: Any = None) -> MT5SessionReport:
    settings = settings or load_mt5_runtime_settings()
    if settings.terminal_path is None:
        return _session_message("terminal_missing", "MT5 terminal path is not configured.")
    if not settings.terminal_path.exists():
        return _session_message(
            "terminal_missing",
            f"Portable MT5 terminal was not found at {settings.terminal_path}",
            terminal_path=settings.terminal_path,
        )

    last_report = _session_message(
        "initialize_failed",
        "MT5 initialize() has not been attempted yet.",
        terminal_path=settings.terminal_path,
    )
    for attempt in range(1, settings.init_retries + 1):
        if attempt > 1:
            time.sleep(settings.init_retry_delay_sec)
        try:
            mt5.shutdown()
        except Exception:
            pass

        init_mode = settings.init_mode
        if init_mode == "auto":
            init_mode = "attach" if settings.auto_launch else "path"

        if init_mode == "attach":
            initialized = mt5.initialize()
        else:
            initialized = mt5.initialize(str(settings.terminal_path))

        if not initialized:
            error = mt5.last_error()
            last_report = _session_message(
                "initialize_failed",
                f"MT5 initialize() failed: [{error[0]}] {error[1]}",
                terminal_path=settings.terminal_path,
                last_error=error,
            )
        else:
            last_report = check_mt5_session(mt5, symbol=symbol, settings=settings)
            if last_report.ready:
                return last_report
            if last_report.state == "no_saved_session":
                return last_report

        _emit(
            logger,
            "warn",
            "MT5 connection attempt did not become ready",
            phase="connection",
            reason=(
                f"attempt={attempt}/{settings.init_retries} init_mode={init_mode} "
                f"state={last_report.state} detail={last_report.message}"
            ),
        )

    return last_report


def wait_for_mt5_terminal(mt5, symbol: str | None = None, settings: MT5RuntimeSettings | None = None, logger: Any = None) -> MT5SessionReport:
    settings = settings or load_mt5_runtime_settings()
    deadline = time.monotonic() + settings.start_timeout_sec
    last_report = _session_message(
        "initialize_failed",
        "MT5 readiness wait has not started yet.",
        terminal_path=settings.terminal_path,
    )

    while time.monotonic() < deadline:
        last_report = connect_mt5_with_retry(mt5, symbol=symbol, settings=settings, logger=logger)
        if last_report.ready or last_report.state in {"terminal_missing", "no_saved_session", "symbol_missing", "symbol_unavailable"}:
            return last_report
        time.sleep(min(5, max(1, settings.init_retry_delay_sec)))

    return last_report
