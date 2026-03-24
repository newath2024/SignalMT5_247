from __future__ import annotations

import datetime as dt

from ..config import SESSION_DEFINITIONS
from .sessions import describe_session_window, format_session_debug_lines


CHECK_DATES = (
    dt.datetime(2026, 3, 24, 12, 0, tzinfo=dt.timezone.utc),
    dt.datetime(2026, 4, 2, 12, 0, tzinfo=dt.timezone.utc),
    dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc),
    dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc),
)


def _utc_window_hours(payload: dict) -> tuple[int, int]:
    return payload["utc_start"].hour, payload["utc_end"].hour


def run_self_check() -> list[str]:
    lines: list[str] = []
    for reference_datetime in CHECK_DATES:
        lines.append(f"[{reference_datetime.date().isoformat()}]")
        for session_name in ("asia", "london"):
            payload = describe_session_window(
                session_name,
                reference_datetime,
                broker_utc_offset_hours=3,
                definitions=SESSION_DEFINITIONS,
                completed_only=True,
            )
            lines.extend(
                f"  {line}"
                for line in format_session_debug_lines(
                    session_name,
                    reference_datetime,
                    broker_utc_offset_hours=3,
                    definitions=SESSION_DEFINITIONS,
                    completed_only=True,
                )
            )

            if session_name == "london":
                expected = {
                    dt.date(2026, 3, 24): (8, 11),
                    dt.date(2026, 4, 2): (7, 10),
                    dt.date(2026, 10, 20): (7, 10),
                    dt.date(2026, 11, 2): (8, 11),
                }[reference_datetime.date()]
                actual = _utc_window_hours(payload)
                if actual != expected:
                    raise AssertionError(
                        f"London session UTC mismatch for {reference_datetime.date().isoformat()}: "
                        f"expected {expected}, got {actual}"
                    )

    return lines


if __name__ == "__main__":
    for line in run_self_check():
        print(line)
