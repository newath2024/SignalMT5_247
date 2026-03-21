from __future__ import annotations

from datetime import datetime


STATE_COLORS = {
    "idle": {"bg": "#e5e7eb", "fg": "#4b5563"},
    "context_found": {"bg": "#fef3c7", "fg": "#92400e"},
    "armed": {"bg": "#fef3c7", "fg": "#92400e"},
    "waiting_mss": {"bg": "#fde68a", "fg": "#92400e"},
    "confirmed": {"bg": "#dbeafe", "fg": "#1d4ed8"},
    "cooldown": {"bg": "#e5e7eb", "fg": "#4b5563"},
    "rejected": {"bg": "#fee2e2", "fg": "#991b1b"},
    "error": {"bg": "#fecaca", "fg": "#7f1d1d"},
}


def state_colors(state: str) -> dict[str, str]:
    return STATE_COLORS.get(state, {"bg": "#f3f4f6", "fg": "#111827"})


def format_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        stamp = datetime.fromisoformat(value)
        return stamp.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def format_short_time(value: str | None) -> str:
    if not value:
        return "-"
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        stamp = datetime.fromisoformat(value)
        return stamp.strftime("%H:%M:%S")
    except ValueError:
        return value


def format_price(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.5f}".rstrip("0").rstrip(".")


def format_zone(top: float | None, bottom: float | None) -> str:
    if top is None or bottom is None:
        return "-"
    lower = min(float(top), float(bottom))
    upper = max(float(top), float(bottom))
    lower_text = f"{lower:.5f}".rstrip("0").rstrip(".")
    upper_text = f"{upper:.5f}".rstrip("0").rstrip(".")
    return f"{lower_text}-{upper_text}"


def format_cooldown(seconds: int | None) -> str:
    if not seconds:
        return "-"
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_score(score: float | None, grade: str | None) -> str:
    if score is None or not grade:
        return "-"
    return f"{grade} {score:.1f}"


def format_phase(value: str | None) -> str:
    if not value:
        return "-"
    labels = {
        "HTF_CONTEXT": "HTF Context",
        "LTF_SWEEP": "LTF Sweep",
        "WAITING_MSS": "Waiting MSS",
        "IFVG_VALIDATION": "iFVG Validation",
        "READY": "Ready",
        "ALERT_SENT": "Alert Sent",
    }
    return labels.get(value, value)


def is_recent(value: str | None, within_sec: int = 300) -> bool:
    if not value:
        return False
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return False
    now = datetime.now(stamp.tzinfo)
    return abs((now - stamp).total_seconds()) <= within_sec


def log_matches_filter(entry: dict, filter_key: str) -> bool:
    level = str(entry.get("level") or "").upper()
    if filter_key == "signals":
        return level in {"WATCH", "SIGNAL"}
    if filter_key == "warnings":
        return level in {"WARN", "ERROR"}
    return True
