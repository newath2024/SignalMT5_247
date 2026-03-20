import datetime as dt


NOTICE_CACHE = set()


def log(message):
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def notify_once(key, message):
    if key in NOTICE_CACHE:
        return
    NOTICE_CACHE.add(key)
    log(message)
