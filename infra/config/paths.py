import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)).resolve() if getattr(sys, "frozen", False) else PROJECT_ROOT


def _default_app_home():
    custom_home = os.getenv("OPENCLAW_HOME")
    if custom_home:
        return Path(custom_home).expanduser().resolve()

    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_app_data).resolve() / "OpenClaw"

    return (Path.home() / ".openclaw").resolve()


APP_HOME = _default_app_home()
LOGS_DIR = Path(os.getenv("OPENCLAW_LOGS_DIR", APP_HOME / "logs")).expanduser().resolve()
RUNTIME_CONFIG_DIR = APP_HOME / "config"
DATA_DIR = APP_HOME / "data"
ENV_FILE = RUNTIME_CONFIG_DIR / ".env"
USER_CONFIG_FILE = RUNTIME_CONFIG_DIR / "user.json"
STATE_FILE = DATA_DIR / "runtime_state.json"
DATABASE_FILE = DATA_DIR / "history.db"
DEFAULT_CONFIG_FILE = BUNDLE_ROOT / "config" / "default.json"
USER_CONFIG_TEMPLATE = BUNDLE_ROOT / "config" / "user.json"
SCHEMA_FILE = BUNDLE_ROOT / "infra" / "storage" / "schema.sql"


def _legacy_project_files():
    candidates = [PROJECT_ROOT]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    return candidates


def legacy_env_candidates():
    return [candidate / ".env" for candidate in _legacy_project_files()]


def legacy_watch_cache_candidates():
    return [candidate / "watch_cache.json" for candidate in _legacy_project_files()]


def legacy_alert_cache_candidates():
    return [candidate / "alert_cache.json" for candidate in _legacy_project_files()]


def ensure_runtime_layout():
    for directory in (APP_HOME, RUNTIME_CONFIG_DIR, DATA_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    if not USER_CONFIG_FILE.exists() and USER_CONFIG_TEMPLATE.exists():
        shutil.copyfile(USER_CONFIG_TEMPLATE, USER_CONFIG_FILE)

    if not ENV_FILE.exists():
        for candidate in legacy_env_candidates():
            if candidate.exists():
                shutil.copyfile(candidate, ENV_FILE)
                break

    return APP_HOME
