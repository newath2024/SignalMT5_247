import datetime as dt
import threading
from collections import deque


LOG_HISTORY_LIMIT = 200
NOTICE_CACHE = set()
_log_history = deque(maxlen=LOG_HISTORY_LIMIT)
_log_lock = threading.RLock()
_notice_lock = threading.Lock()


def _build_log_entry(message, timestamp=None):
    if timestamp is None:
        timestamp = dt.datetime.now()
    return {
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "label": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "message": str(message),
    }


def log(message):
    entry = _build_log_entry(message)
    with _log_lock:
        _log_history.append(entry)
    print(f"[{entry['label']}] {entry['message']}", flush=True)


def get_recent_logs(limit=50):
    with _log_lock:
        history = list(_log_history)
    if limit is None or limit >= len(history):
        return history
    return history[-limit:]


def notify_once(key, message):
    with _notice_lock:
        if key in NOTICE_CACHE:
            return
        NOTICE_CACHE.add(key)
    log(message)
