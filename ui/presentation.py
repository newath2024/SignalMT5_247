from __future__ import annotations

from datetime import datetime


STATE_META = {
    "idle": {
        "label": "Standby",
        "bg": "#e5e7eb",
        "fg": "#4b5563",
        "icon": "⚪",
        "severity": "neutral",
    },
    "context_found": {
        "label": "Tracking",
        "bg": "#fef3c7",
        "fg": "#92400e",
        "icon": "🟡",
        "severity": "watch",
    },
    "watch_armed": {
        "label": "Locked Target",
        "bg": "#dcfce7",
        "fg": "#166534",
        "icon": "🟢",
        "severity": "watch",
    },
    "armed": {
        "label": "Locked Target",
        "bg": "#dcfce7",
        "fg": "#166534",
        "icon": "🟢",
        "severity": "watch",
    },
    "setup_building": {
        "label": "Tracking",
        "bg": "#fde68a",
        "fg": "#92400e",
        "icon": "🟡",
        "severity": "watch",
    },
    "waiting_mss": {
        "label": "Tracking MSS",
        "bg": "#fde68a",
        "fg": "#92400e",
        "icon": "🟡",
        "severity": "watch",
    },
    "entry_ready": {
        "label": "Locked Target",
        "bg": "#dcfce7",
        "fg": "#166534",
        "icon": "🟢",
        "severity": "signal",
    },
    "confirmed": {
        "label": "Locked Target",
        "bg": "#dcfce7",
        "fg": "#166534",
        "icon": "🟢",
        "severity": "signal",
    },
    "alerted": {
        "label": "Alert Routed",
        "bg": "#dcfce7",
        "fg": "#166534",
        "icon": "🟢",
        "severity": "signal",
    },
    "cooldown": {
        "label": "Cooling Down",
        "bg": "#e5e7eb",
        "fg": "#4b5563",
        "icon": "⚪",
        "severity": "neutral",
    },
    "rejected": {
        "label": "Invalid / No Edge",
        "bg": "#fee2e2",
        "fg": "#991b1b",
        "icon": "🔴",
        "severity": "warning",
    },
    "expired": {
        "label": "Context Invalid",
        "bg": "#fee2e2",
        "fg": "#991b1b",
        "icon": "🔴",
        "severity": "warning",
    },
    "error": {
        "label": "Attention",
        "bg": "#fecaca",
        "fg": "#7f1d1d",
        "icon": "🔴",
        "severity": "error",
    },
}


UNKNOWN_STATE_META = {
    "label": "Unknown",
    "bg": "#f3f4f6",
    "fg": "#111827",
    "icon": "⚪",
    "severity": "neutral",
}


LIQUIDITY_SHORT_LABELS = {
    "Previous Day High": "PDH",
    "Previous Day Low": "PDL",
    "Previous Week High": "PWH",
    "Previous Week Low": "PWL",
    "Asia Session High": "ASH",
    "Asia Session Low": "ASL",
    "London Session High": "LOH",
    "London Session Low": "LOL",
}


PRIORITY_META = {
    "high": {"label": "High", "rank": 0, "actionable": True},
    "medium": {"label": "Medium", "rank": 1, "actionable": False},
    "low": {"label": "Low", "rank": 2, "actionable": False},
}


SCANNER_STATUS_META = {
    "idle": {
        "label": "STANDBY",
        "dot": "#94a3b8",
        "dot_pulse": "#cbd5e1",
    },
    "starting": {
        "label": "ARMING",
        "dot": "#f59e0b",
        "dot_pulse": "#fbbf24",
    },
    "scanning": {
        "label": "HUNTING",
        "dot": "#f59e0b",
        "dot_pulse": "#fcd34d",
    },
    "running": {
        "label": "ARMED",
        "dot": "#16a34a",
        "dot_pulse": "#4ade80",
    },
    "stopping": {
        "label": "DISARMING",
        "dot": "#ef4444",
        "dot_pulse": "#f87171",
    },
    "stopped": {
        "label": "DISARMED",
        "dot": "#ef4444",
        "dot_pulse": "#ef4444",
    },
    "error": {
        "label": "ATTENTION",
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


def get_state_icon(state: str | None) -> str:
    return str(get_state_meta(state)["icon"])


def get_state_badge(state: str | None) -> str:
    meta = get_state_meta(state)
    return f"{meta['icon']} {meta['label']}"


def state_colors(state: str | None) -> dict[str, str]:
    meta = get_state_meta(state)
    return {"bg": str(meta["bg"]), "fg": str(meta["fg"])}


def _timestamp_value(value) -> float:
    stamp = _coerce_datetime(value)
    return stamp.timestamp() if stamp else 0.0


def abbreviate_liquidity_label(text: str | None) -> str:
    value = str(text or "").strip()
    if not value:
        return "-"
    for long_label, short_label in LIQUIDITY_SHORT_LABELS.items():
        value = value.replace(long_label, short_label)
    return value


def _extract_liquidity_label(*values) -> str | None:
    for value in values:
        lowered = str(value or "").lower()
        for label in LIQUIDITY_SHORT_LABELS:
            if label.lower() in lowered:
                return label
    return None


def _normalize_liquidity_state(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"swept_and_reclaimed", "sweep + reclaim"}:
        return "Sweep + reclaim"
    if text == "swept":
        return "Swept"
    if text == "tapped":
        return "Tapped"
    if text in {"at", "untouched"}:
        return "At"
    return ""


def format_htf_context_short(row: dict | None) -> str:
    payload = dict(row or {})
    detail = dict(payload.get("detail") or {})
    raw_context = str(detail.get("htf_context") or payload.get("htf_context") or "-").strip()
    zone_type = str(detail.get("htf_zone_type") or "").strip()
    liquidity_state = _normalize_liquidity_state(detail.get("liquidity_interaction_state"))
    liquidity_label = _extract_liquidity_label(raw_context, zone_type, detail.get("zone"), detail.get("htf_zone_source"))

    if liquidity_label:
        short_label = LIQUIDITY_SHORT_LABELS[liquidity_label]
        if liquidity_state:
            return f"{liquidity_state} {short_label}".strip()
        return short_label

    if zone_type and zone_type != "-":
        return abbreviate_liquidity_label(zone_type)
    return abbreviate_liquidity_label(raw_context)


def format_symbol_focus(row: dict | None) -> str:
    payload = dict(row or {})
    state = str(payload.get("state") or "").lower()
    reason = str(payload.get("reason") or "").strip()

    if state in {"confirmed", "entry_ready"}:
        return "Target locked"
    if state in {"armed", "watch_armed"}:
        return "Target locked"
    if state in {"waiting_mss", "setup_building"}:
        return "Tracking MSS after sweep"
    if state == "context_found":
        return "Tracking LTF sweep" if "ltf sweep" in reason.lower() else "Tracking HTF trigger"
    if state == "rejected":
        if "strict ifvg" in reason.lower():
            return "No strict iFVG"
        return reason.replace("rejected:", "").strip() or "No edge"
    if state == "cooldown":
        return "Cooldown"
    if state == "error":
        return "Operator attention"
    return "No edge yet"


def get_priority_meta(row: dict | None) -> dict[str, str | int | bool]:
    payload = dict(row or {})
    state = str(payload.get("state") or "").lower()
    phase = str(payload.get("phase") or "").upper()

    if state in {"confirmed", "entry_ready", "armed", "watch_armed", "waiting_mss"}:
        return PRIORITY_META["high"]
    if state == "context_found":
        return PRIORITY_META["medium"] if phase == "LTF_SWEEP" else PRIORITY_META["low"]
    return PRIORITY_META["low"]


def get_priority_label(row: dict | None) -> str:
    return str(get_priority_meta(row)["label"])


def is_actionable_symbol(row: dict | None) -> bool:
    return bool(get_priority_meta(row)["actionable"])


def sort_symbol_rows(rows: list[dict] | None) -> list[dict]:
    items = list(rows or [])
    return sorted(
        items,
        key=lambda item: (
            int(get_priority_meta(item)["rank"]),
            -float(item.get("score") or 0.0),
            -_timestamp_value(item.get("last_update")),
            str(item.get("symbol") or ""),
        ),
    )


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
        "HTF_CONTEXT": "HTF Thesis",
        "LTF_SWEEP": "Sweep Tracking",
        "WAITING_MSS": "Tracking MSS",
        "IFVG_VALIDATION": "iFVG Validation",
        "READY": "Locked Target",
        "ALERT_SENT": "Alert Routed",
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
