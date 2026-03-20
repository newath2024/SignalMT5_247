import json
import time

from .config import WATCH_ALERTED_RETENTION_SEC, WATCH_CACHE_FILE

_watch_cache = {}


def _to_jsonable(value):
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _persist_watch_cache():
    WATCH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "watches": [_to_jsonable(watch_setup) for watch_setup in _watch_cache.values()],
    }
    temp_path = WATCH_CACHE_FILE.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(WATCH_CACHE_FILE)


def _load_watch_cache():
    if not WATCH_CACHE_FILE.exists():
        return

    try:
        payload = json.loads(WATCH_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    if isinstance(payload, dict):
        raw_watches = payload.get("watches", [])
    elif isinstance(payload, list):
        raw_watches = payload
    else:
        raw_watches = []

    for raw_watch in raw_watches:
        if not isinstance(raw_watch, dict):
            continue
        if not all(key in raw_watch for key in ("symbol", "bias", "timeframe", "htf_context", "ifvg")):
            continue

        raw_watch["watch_key"] = raw_watch.get("watch_key") or build_watch_key(raw_watch)
        raw_watch["status"] = raw_watch.get("status", "watch")
        _watch_cache[raw_watch["watch_key"]] = raw_watch


def cleanup_persisted_watches(now=None, persist=True):
    if now is None:
        now = time.time()

    removed_any = False
    expired_keys = []
    for watch_key, watch_setup in _watch_cache.items():
        if watch_setup.get("status") != "alerted":
            continue
        alerted_at = watch_setup.get("alerted_at")
        if alerted_at is None:
            expired_keys.append(watch_key)
            continue
        try:
            age = now - float(alerted_at)
        except (TypeError, ValueError):
            expired_keys.append(watch_key)
            continue
        if age > WATCH_ALERTED_RETENTION_SEC:
            expired_keys.append(watch_key)

    for watch_key in expired_keys:
        _watch_cache.pop(watch_key, None)
        removed_any = True

    if removed_any and persist:
        _persist_watch_cache()


def get_watch_cache_count(statuses=None):
    cleanup_persisted_watches()
    if statuses is None:
        return len(_watch_cache)
    return sum(1 for watch_setup in _watch_cache.values() if watch_setup["status"] in statuses)


def get_watch_cache_file():
    return WATCH_CACHE_FILE


def build_watch_key(watch_setup):
    ifvg = watch_setup["ifvg"]
    return (
        f"{watch_setup['symbol']}|{watch_setup['bias']}|{watch_setup['timeframe']}|"
        f"{watch_setup['htf_context']}|{ifvg['source_index']}|"
        f"{round(float(ifvg['low']), 8)}|{round(float(ifvg['high']), 8)}"
    )


def get_watch_setup(watch_key):
    cleanup_persisted_watches()
    return _watch_cache.get(watch_key)


def get_symbol_watches(symbol, statuses=("watch",)):
    cleanup_persisted_watches()
    return [
        watch_setup
        for watch_setup in _watch_cache.values()
        if watch_setup["symbol"] == symbol and watch_setup["status"] in statuses
    ]


def upsert_watch_setup(watch_setup):
    watch_key = build_watch_key(watch_setup)
    existing = _watch_cache.get(watch_key)
    if existing is not None:
        existing.update(
            {
                "context": watch_setup["context"],
                "htf_zone": watch_setup["htf_zone"],
                "sweep_index": watch_setup["sweep_index"],
                "sweep_price": watch_setup["sweep_price"],
                "structure_level": watch_setup["structure_level"],
                "sweep_quality": watch_setup["sweep_quality"],
                "swept_liquidity": watch_setup["swept_liquidity"],
                "avg_range": watch_setup["avg_range"],
                "ifvg": watch_setup["ifvg"],
                "watch_index": watch_setup["watch_index"],
                "invalidation_price": watch_setup["invalidation_price"],
            }
        )
        _persist_watch_cache()
        return False, existing

    watch_setup["watch_key"] = watch_key
    _watch_cache[watch_key] = watch_setup
    _persist_watch_cache()
    return True, watch_setup


def mark_watch_alerted(watch_key, mss_index):
    watch_setup = _watch_cache.get(watch_key)
    if watch_setup is None:
        return None

    watch_setup["status"] = "alerted"
    watch_setup["alerted_mss_index"] = mss_index
    watch_setup["alerted_at"] = time.time()
    _persist_watch_cache()
    return watch_setup


def remove_watch_setup(watch_key):
    removed = _watch_cache.pop(watch_key, None)
    if removed is not None:
        _persist_watch_cache()
    return removed


_load_watch_cache()
cleanup_persisted_watches(persist=False)
