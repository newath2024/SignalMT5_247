import json
import threading
import time

from .config import ALERT_CACHE_FILE, ALERT_CACHE_RETENTION_SEC, ALERT_COOLDOWN_SEC

_alert_cache = {}
_alert_lock = threading.RLock()


def _persist_alert_cache():
    with _alert_lock:
        payload = {
            "version": 1,
            "alerts": dict(_alert_cache),
        }

    ALERT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = ALERT_CACHE_FILE.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(ALERT_CACHE_FILE)


def cleanup_alert_cache(now=None, persist=True):
    if now is None:
        now = time.time()

    with _alert_lock:
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

    with _alert_lock:
        for setup_key, sent_at in raw_alerts.items():
            try:
                _alert_cache[str(setup_key)] = float(sent_at)
            except (TypeError, ValueError):
                continue

    cleanup_alert_cache(persist=False)


def can_send_alert(setup_key, cooldown_sec=None, now=None):
    if now is None:
        now = time.time()
    if cooldown_sec is None:
        cooldown_sec = ALERT_COOLDOWN_SEC

    cleanup_alert_cache(now=now)
    with _alert_lock:
        last_sent = _alert_cache.get(setup_key)
    return last_sent is None or now - last_sent >= cooldown_sec


def mark_alert_sent(setup_key, sent_at=None):
    if sent_at is None:
        sent_at = time.time()

    with _alert_lock:
        _alert_cache[setup_key] = float(sent_at)
    cleanup_alert_cache(now=sent_at, persist=False)
    _persist_alert_cache()


def _parse_setup_key(setup_key):
    parts = str(setup_key).split("|")
    if len(parts) < 6:
        return {
            "symbol": str(setup_key),
            "bias": "Unknown",
            "timeframe": "-",
            "htf_context": "-",
            "entry_price": None,
            "stop_loss": None,
        }

    return {
        "symbol": parts[0],
        "bias": parts[1],
        "timeframe": parts[2],
        "htf_context": parts[3],
        "entry_price": parts[4],
        "stop_loss": parts[5],
    }


def list_recent_alerts(limit=None):
    cleanup_alert_cache()
    with _alert_lock:
        alerts = sorted(_alert_cache.items(), key=lambda item: item[1], reverse=True)

    if limit is not None:
        alerts = alerts[:limit]

    items = []
    for setup_key, sent_at in alerts:
        payload = _parse_setup_key(setup_key)
        payload.update(
            {
                "setup_key": setup_key,
                "sent_at": float(sent_at),
            }
        )
        items.append(payload)
    return items


def get_alert_cache_count():
    cleanup_alert_cache()
    with _alert_lock:
        return len(_alert_cache)


def get_alert_cache_file():
    return ALERT_CACHE_FILE


_load_alert_cache()
