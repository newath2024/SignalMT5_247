import os
import sys
from pathlib import Path

ALERT_COOLDOWN_SEC = 1800
DEFAULT_POLL_INTERVAL_SEC = 60
ALERT_CACHE_RETENTION_SEC = 6 * 3600
WATCH_ALERTED_RETENTION_SEC = 12 * 3600

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

ENV_FILE = BASE_DIR / ".env"
WATCH_CACHE_FILE = BASE_DIR / "watch_cache.json"
ALERT_CACHE_FILE = BASE_DIR / "alert_cache.json"


def load_local_env(path=ENV_FILE):
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def save_local_env_value(key, value, path=ENV_FILE):
    env_values = load_local_env(path)
    env_values[key] = str(value)

    lines = [
        "# Local secrets for MT5 scanner",
        f"TELEGRAM_BOT_TOKEN={env_values.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_CHAT_ID={env_values.get('TELEGRAM_CHAT_ID', '')}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


LOCAL_ENV = load_local_env()

TELEGRAM_BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or LOCAL_ENV.get("TELEGRAM_BOT_TOKEN")
    or "YOUR_TELEGRAM_BOT_TOKEN"
).strip()
TELEGRAM_CHAT_ID = (
    os.getenv("TELEGRAM_CHAT_ID")
    or LOCAL_ENV.get("TELEGRAM_CHAT_ID")
    or "YOUR_TELEGRAM_CHAT_ID"
).strip()
