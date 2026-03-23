from __future__ import annotations

import os
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_path(value: str, root: Path) -> str:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return str(candidate.resolve())


def load_portable_environment(root: Path) -> dict[str, str]:
    root = root.resolve()
    env_path = root / "portable.env"
    file_values = _read_env_file(env_path)
    merged = dict(os.environ)
    merged.update(file_values)

    merged.setdefault("OPENCLAW_PORTABLE_ROOT", str(root))
    merged.setdefault("OPENCLAW_HOME", str((root / "runtime").resolve()))
    merged.setdefault("OPENCLAW_LOGS_DIR", str((root / "logs").resolve()))
    merged.setdefault("OPENCLAW_MT5_TERMINAL", str((root / "mt5_portable" / "terminal64.exe").resolve()))
    merged.setdefault("OPENCLAW_MT5_WINDOW_MODE", "normal")
    merged.setdefault("OPENCLAW_MT5_AUTO_LAUNCH", "true")
    merged.setdefault("OPENCLAW_MT5_START_TIMEOUT_SEC", "90")
    merged.setdefault("OPENCLAW_MT5_INIT_RETRIES", "15")
    merged.setdefault("OPENCLAW_MT5_INIT_RETRY_DELAY_SEC", "3")
    merged.setdefault("OPENCLAW_MT5_REQUIRE_SAVED_SESSION", "true")
    merged.setdefault("OPENCLAW_MT5_TICK_MAX_AGE_SEC", "0")
    merged.setdefault("OPENCLAW_BOT_RUN_MODE", "headless")
    merged.setdefault("OPENCLAW_BOT_RESTART_DELAY_SEC", "10")
    merged.setdefault("OPENCLAW_APP_ARGS", "")

    merged["OPENCLAW_PORTABLE_ROOT"] = _resolve_path(merged["OPENCLAW_PORTABLE_ROOT"], root)
    merged["OPENCLAW_HOME"] = _resolve_path(merged["OPENCLAW_HOME"], root)
    merged["OPENCLAW_LOGS_DIR"] = _resolve_path(merged["OPENCLAW_LOGS_DIR"], root)
    merged["OPENCLAW_MT5_TERMINAL"] = _resolve_path(merged["OPENCLAW_MT5_TERMINAL"], root)
    merged["OPENCLAW_PORTABLE_ENV"] = str(env_path.resolve())
    return merged
