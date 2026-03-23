from __future__ import annotations

import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import MetaTrader5 as mt5

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import load_app_config
from core.mt5_runtime import apply_mt5_window_mode, launch_mt5_terminal, load_mt5_runtime_settings, wait_for_mt5_terminal
from tools.portable.env_loader import load_portable_environment


def _build_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("openclaw.portable.launcher")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def _resolve_python_executable(root: Path) -> Path:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / "python_embedded" / "python.exe",
        Path(sys.executable).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No local Python runtime was found. Expected .venv\\Scripts\\python.exe or python_embedded\\python.exe.")


def main() -> int:
    root = ROOT
    env = load_portable_environment(root)
    os.environ.update(env)

    logs_dir = Path(env["OPENCLAW_LOGS_DIR"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = _build_logger(logs_dir / "launcher.log")

    settings = load_mt5_runtime_settings()
    terminal_path = settings.terminal_path
    if terminal_path is None or not terminal_path.exists():
        logger.error("Portable MT5 terminal was not found at %s", terminal_path)
        logger.error("Place a portable MT5 terminal under mt5_portable\\terminal64.exe before running this launcher.")
        return 2

    python_executable = _resolve_python_executable(root)
    logger.info("Portable root: %s", root)
    logger.info("Python runtime: %s", python_executable)
    logger.info("MT5 terminal: %s", terminal_path)

    try:
        config = load_app_config()
        probe_symbol = next(iter(config.scanner.symbols), None)
    except Exception as exc:
        logger.warning("Could not load app config before MT5 readiness check: %s", exc)
        probe_symbol = None

    mt5_process = None
    if settings.auto_launch:
        try:
            mt5_process = launch_mt5_terminal(settings=settings)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            return 2
        except Exception as exc:
            logger.error("Failed to launch MT5 portable terminal: %s", exc)
            return 2

    report = wait_for_mt5_terminal(mt5, symbol=probe_symbol, settings=settings, logger=logger)
    if report.ready:
        logger.info("MT5 ready: %s", report.message)
        apply_mt5_window_mode(mt5_process.pid if mt5_process else None, settings=settings, logger=logger)
    elif report.state == "no_saved_session":
        logger.error(report.message)
        return 3
    else:
        logger.error(
            "MT5 did not become ready within %ss. Last status: %s",
            settings.start_timeout_sec,
            report.message,
        )
        return 4

    try:
        mt5.shutdown()
    except Exception:
        pass

    restart_script = root / "restart_bot.bat"
    if not restart_script.exists():
        logger.error("restart_bot.bat is missing at %s", restart_script)
        return 5

    child_env = dict(env)
    child_env["OPENCLAW_PYTHON_EXE"] = str(python_executable)
    logger.info("Starting supervised bot loop...")
    completed = subprocess.call(
        ["cmd.exe", "/c", str(restart_script)],
        cwd=str(root),
        env=child_env,
    )
    logger.info("Supervisor exited with code %s", completed)
    return int(completed)


if __name__ == "__main__":
    raise SystemExit(main())
