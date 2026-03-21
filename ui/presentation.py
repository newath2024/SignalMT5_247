from __future__ import annotations

from datetime import datetime


STATE_META = {
    "idle": {
        "label": "Idle",
        "bg": "#e5e7eb",
        "fg": "#4b5563",
        "severity": "neutral",
    },
    "context_found": {
        "label": "HTF Context",
        "bg": "#fef3c7",
        "fg": "#92400e",
        "severity": "watch",
    },
    "watch_armed": {
        "label": "Watching Setup",
        "bg": "#fef3c7",
        "fg": "#92400e",
        "severity": "watch",
    },
    "armed": {
        "label": "Watching Setup",
        "bg": "#fef3c7",
        "fg": "#92400e",
        "severity": "watch",
    },
    "setup_building": {
        "label": "Setup Forming",
        "bg": "#fde68a",
        "fg": "#92400e",
        "severity": "watch",
    },
    "waiting_mss": {
        "label": "Setup Forming",
        "bg": "#fde68a",
        "fg": "#92400e",
        "severity": "watch",
    },
    "entry_ready": {
        "label": "Ready to Enter",
        "bg": "#dbeafe",
        "fg": "#1d4ed8",
        "severity": "signal",
    },
    "confirmed": {
        "label": "Ready to Enter",
        "bg": "#dbeafe",
        "fg": "#1d4ed8",
        "severity": "signal",
    },
    "alerted": {
        "label": "Signal Sent",
        "bg": "#dbeafe",
        "fg": "#1d4ed8",
        "severity": "signal",
    },
    "cooldown": {
        "label": "Cooling Down",
        "bg": "#e5e7eb",
        "fg": "#4b5563",
        "severity": "neutral",
    },
    "rejected": {
        "label": "Setup Rejected",
        "bg": "#fee2e2",
        "fg": "#991b1b",
        "severity": "warning",
    },
    "expired": {
        "label": "Context Invalid",
        "bg": "#fee2e2",
        "fg": "#991b1b",
        "severity": "warning",
    },
    "error": {
        "label": "Error",
        "bg": "#fecaca",
        "fg": "#7f1d1d",
        "severity": "error",
    },
}


UNKNOWN_STATE_META = {
    "label": "Unknown",
    "bg": "#f3f4f6",
    "fg": "#111827",
    "severity": "neutral",
}


SCANNER_STATUS_META = {
    "idle": {
        "label": "IDLE",
        "dot": "#94a3b8",
        "dot_pulse": "#cbd5e1",
    },
    "starting": {
        "label": "STARTING",
        "dot": "#f59e0b",
        "dot_pulse": "#fbbf24",
    },
    "scanning": {
        "label": "SCANNING",
        "dot": "#f59e0b",
        "dot_pulse": "#fcd34d",
    },
    "running": {
        "label": "RUNNING",
        "dot": "#16a34a",
        "dot_pulse": "#4ade80",
    },
    "stopping": {
        "label": "STOPPING",
        "dot": "#ef4444",
        "dot_pulse": "#f87171",
    },
    "stopped": {
        "label": "STOPPED",
        "dot": "#ef4444",
        "dot_pulse": "#ef4444",
    },
    "error": {
        "label": "ERROR",
        "dot": "#dc2626",
        "dot_pulse": "#f87171",
    },
}


def get_state_meta(state: str | None) -> dict[str, str]:
    key = str(state or "").strip()
    if not key:
        return UNKNOWN_STATE_META
    return STATE_META.get(key, {**UNKNOWN_STATE_META, "label": key.replace("_", " ").title()})


def get_state_label(state: str | None) -> str:
    return str(get_state_meta(state)["label"])


def state_colors(state: str | None) -> dict[str, str]:
    meta = get_state_meta(state)
    return {"bg": str(meta["bg"]), "fg": str(meta["fg"])}


def _coerce_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone() if value.tzinfo else value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).astimezone()
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        stamp = datetime.fromisoformat(text)
        return stamp.astimezone() if stamp.tzinfo else stamp
    except ValueError:
        return None


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_timestamp(value: str | None) -> str:
    stamp = _coerce_datetime(value)
    if not stamp:
        return "-"
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


def format_short_time(value: str | None) -> str:
    stamp = _coerce_datetime(value)
    if not stamp:
        return "-"
    return stamp.strftime("%H:%M:%S")


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
    return format_duration(seconds)


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
    stamp = _coerce_datetime(value)
    if not stamp:
        return False
    now = datetime.now(stamp.tzinfo)
    return abs((now - stamp).total_seconds()) <= within_sec


def format_relative_age(value, now: datetime | None = None) -> str:
    stamp = _coerce_datetime(value)
    if not stamp:
        return "-"
    current = now or datetime.now(stamp.tzinfo)
    delta_seconds = max(0, int((current - stamp).total_seconds()))
    if delta_seconds == 0:
        return "just now"
    return f"{format_duration(delta_seconds)} ago"


def get_scanner_status_meta(status: str | None, pulse: bool = False) -> dict[str, str]:
    key = str(status or "").strip().lower()
    meta = SCANNER_STATUS_META.get(key, SCANNER_STATUS_META["idle"])
    dot = meta["dot_pulse"] if pulse and meta["dot_pulse"] != meta["dot"] else meta["dot"]
    return {
        "label": str(meta["label"]),
        "dot": str(dot),
    }


def log_matches_filter(entry: dict, filter_key: str) -> bool:
    level = str(entry.get("level") or "").upper()
    if filter_key == "signals":
        return level in {"WATCH", "SIGNAL"}
    if filter_key == "warnings":
        return level in {"WARN", "ERROR"}
    return True
