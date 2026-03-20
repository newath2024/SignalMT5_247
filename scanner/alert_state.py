import json
import time

from .config import ALERT_CACHE_FILE, ALERT_CACHE_RETENTION_SEC

_alert_cache = {}


def _persist_alert_cache():
    ALERT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "alerts": _alert_cache,
    }
    temp_path = ALERT_CACHE_FILE.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(ALERT_CACHE_FILE)


def cleanup_alert_cache(now=None, persist=True):
    if now is None:
        now = time.time()

    expired_keys = [
        setup_key
        for setup_key, sent_at in _alert_cache.items()
        if now - float(sent_at) > ALERT_CACHE_RETENTION_SEC
    ]
    for setup_key in expired_keys:
        _alert_cache.pop(setup_key, None)

    if expired_keys and persist:
        _persist_alert_cache()


def _load_alert_cache():
    if not ALERT_CACHE_FILE.exists():
        return

    try:
        payload = json.loads(ALERT_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    raw_alerts = payload.get("alerts", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw_alerts, dict):
        return

    for setup_key, sent_at in raw_alerts.items():
        try:
            _alert_cache[str(setup_key)] = float(sent_at)
        except (TypeError, ValueError):
            continue

    cleanup_alert_cache(persist=False)


def can_send_alert(setup_key, cooldown_sec, now=None):
    if now is None:
        now = time.time()

    cleanup_alert_cache(now=now)
    last_sent = _alert_cache.get(setup_key)
    return last_sent is None or now - last_sent >= cooldown_sec


def mark_alert_sent(setup_key, sent_at=None):
    if sent_at is None:
        sent_at = time.time()

    _alert_cache[setup_key] = float(sent_at)
    cleanup_alert_cache(now=sent_at, persist=False)
    _persist_alert_cache()


def get_alert_cache_count():
    cleanup_alert_cache()
    return len(_alert_cache)


def get_alert_cache_file():
    return ALERT_CACHE_FILE


_load_alert_cache()
