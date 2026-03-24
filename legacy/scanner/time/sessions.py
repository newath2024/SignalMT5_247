from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import tz

from ..config import SESSION_DEFINITIONS


UTC = dt.timezone.utc


def _ensure_aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _broker_timezone(offset_hours: int | float) -> dt.tzinfo:
    return dt.timezone(dt.timedelta(hours=float(offset_hours or 0.0)))


def _resolve_timezone(timezone_name: str) -> dt.tzinfo:
    key = str(timezone_name or "").strip()
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        fallback = tz.gettz(key)
        if fallback is None:
            raise
        return fallback


def _session_definition(session_name: str, definitions: dict | None = None) -> dict:
    session_key = str(session_name or "").strip().lower()
    mapping = definitions or SESSION_DEFINITIONS
    if session_key not in mapping:
        raise KeyError(f"Unknown session definition: {session_name}")
    return dict(mapping[session_key])


def _local_session_bounds(session_definition: dict, reference_date_local: dt.date) -> tuple[dt.datetime, dt.datetime]:
    zone = _resolve_timezone(str(session_definition["timezone"]))
    start_hour = int(session_definition["start_hour_local"])
    end_hour = int(session_definition["end_hour_local"])

    start_local = dt.datetime.combine(
        reference_date_local,
        dt.time(start_hour, 0),
        tzinfo=zone,
    )
    end_local = dt.datetime.combine(
        reference_date_local,
        dt.time(end_hour, 0),
        tzinfo=zone,
    )

    # Sessions such as Asia can cross UTC midnight after conversion, and future
    # sessions may also cross local midnight. We treat end <= start as an
    # overnight local session and roll the end into the next local day.
    if end_local <= start_local:
        end_local += dt.timedelta(days=1)

    return start_local, end_local


def build_session_window_from_timezone(
    timezone_name: str,
    start_hour_local: int,
    end_hour_local: int,
    reference_date_local: dt.date,
) -> tuple[dt.datetime, dt.datetime]:
    session_definition = {
        "timezone": timezone_name,
        "start_hour_local": int(start_hour_local),
        "end_hour_local": int(end_hour_local),
    }
    return _local_session_bounds(session_definition, reference_date_local)


def get_session_window_utc(session_name: str, reference_datetime: dt.datetime, definitions: dict | None = None) -> tuple[dt.datetime, dt.datetime]:
    session_definition = _session_definition(session_name, definitions=definitions)
    reference_utc = _ensure_aware(reference_datetime).astimezone(UTC)
    session_zone = _resolve_timezone(str(session_definition["timezone"]))
    reference_local = reference_utc.astimezone(session_zone)
    start_local, end_local = _local_session_bounds(session_definition, reference_local.date())
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def get_completed_session_window_utc(
    session_name: str,
    reference_datetime: dt.datetime,
    definitions: dict | None = None,
) -> tuple[dt.datetime, dt.datetime]:
    reference_utc = _ensure_aware(reference_datetime).astimezone(UTC)
    start_utc, end_utc = get_session_window_utc(session_name, reference_utc, definitions=definitions)
    if reference_utc < end_utc:
        previous_reference = reference_utc - dt.timedelta(days=1)
        start_utc, end_utc = get_session_window_utc(session_name, previous_reference, definitions=definitions)
    return start_utc, end_utc


def get_session_window_broker(
    session_name: str,
    broker_now: dt.datetime,
    broker_utc_offset_hours: int | float,
    definitions: dict | None = None,
    *,
    completed_only: bool = True,
) -> tuple[dt.datetime, dt.datetime]:
    reference_utc = _ensure_aware(broker_now).astimezone(UTC)
    if completed_only:
        start_utc, end_utc = get_completed_session_window_utc(session_name, reference_utc, definitions=definitions)
    else:
        start_utc, end_utc = get_session_window_utc(session_name, reference_utc, definitions=definitions)
    broker_tz = _broker_timezone(broker_utc_offset_hours)
    return start_utc.astimezone(broker_tz), end_utc.astimezone(broker_tz)


def is_session_active(
    session_name: str,
    broker_now: dt.datetime,
    broker_utc_offset_hours: int | float,
    definitions: dict | None = None,
) -> bool:
    reference_utc = _ensure_aware(broker_now).astimezone(UTC)
    start_utc, end_utc = get_session_window_utc(session_name, reference_utc, definitions=definitions)
    return start_utc <= reference_utc < end_utc


def describe_session_window(
    session_name: str,
    reference_datetime: dt.datetime,
    broker_utc_offset_hours: int | float,
    definitions: dict | None = None,
    *,
    completed_only: bool = True,
) -> dict:
    session_definition = _session_definition(session_name, definitions=definitions)
    reference_utc = _ensure_aware(reference_datetime).astimezone(UTC)
    if completed_only:
        start_utc, end_utc = get_completed_session_window_utc(session_name, reference_utc, definitions=definitions)
    else:
        start_utc, end_utc = get_session_window_utc(session_name, reference_utc, definitions=definitions)

    session_zone = _resolve_timezone(str(session_definition["timezone"]))
    broker_tz = _broker_timezone(broker_utc_offset_hours)
    start_local = start_utc.astimezone(session_zone)
    end_local = end_utc.astimezone(session_zone)
    start_broker = start_utc.astimezone(broker_tz)
    end_broker = end_utc.astimezone(broker_tz)

    return {
        "name": session_name,
        "label": session_definition["label"],
        "timezone": session_definition["timezone"],
        "start_hour_local": int(session_definition["start_hour_local"]),
        "end_hour_local": int(session_definition["end_hour_local"]),
        "local_start": start_local,
        "local_end": end_local,
        "utc_start": start_utc,
        "utc_end": end_utc,
        "broker_start": start_broker,
        "broker_end": end_broker,
        "completed_only": completed_only,
    }


def format_session_debug_lines(
    session_name: str,
    reference_datetime: dt.datetime,
    broker_utc_offset_hours: int | float,
    definitions: dict | None = None,
    *,
    completed_only: bool = True,
) -> list[str]:
    payload = describe_session_window(
        session_name,
        reference_datetime,
        broker_utc_offset_hours,
        definitions=definitions,
        completed_only=completed_only,
    )
    label = payload["label"]
    timezone_name = payload["timezone"]
    return [
        (
            f"{label} session local: "
            f"{payload['local_start'].strftime('%Y-%m-%d %H:%M')} - "
            f"{payload['local_end'].strftime('%Y-%m-%d %H:%M')} {timezone_name}"
        ),
        (
            f"{label} session UTC: "
            f"{payload['utc_start'].strftime('%Y-%m-%d %H:%M')} - "
            f"{payload['utc_end'].strftime('%Y-%m-%d %H:%M')} UTC"
        ),
        (
            f"{label} session broker: "
            f"{payload['broker_start'].strftime('%Y-%m-%d %H:%M')} - "
            f"{payload['broker_end'].strftime('%Y-%m-%d %H:%M')} "
            f"UTC{payload['broker_start'].strftime('%z')}"
        ),
    ]
