from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ui.presentation import format_duration, format_relative_age, format_short_time, format_timestamp


@dataclass(frozen=True)
class MetricCardVM:
    value: str
    hint: str


@dataclass(frozen=True)
class StatusHeaderVM:
    headline: str
    progress_text: str
    last_scan_text: str


def build_metric_card_models(metrics: dict[str, Any], scanner: dict[str, Any]) -> dict[str, MetricCardVM]:
    """Map the runtime snapshot into the metric cards shown in the header."""
    return {
        "active_watches": MetricCardVM(
            value=str(metrics["active_watches"]),
            hint="Markets currently being tracked for MSS and iFVG execution alignment.",
        ),
        "confirmed_signals": MetricCardVM(
            value=str(metrics["confirmed_signals_today"]),
            hint="Confirmed sniper entries recorded in local history during the current session.",
        ),
        "coverage": MetricCardVM(
            value=f"{metrics['scanned_symbols']}/{metrics['total_symbols']}",
            hint="Markets processed by the active sweep engine during this runtime session.",
        ),
        "loop_interval": MetricCardVM(
            value=f"{scanner['interval_sec']}s",
            hint="Configured delay before the next automated sweep check begins.",
        ),
    }


def build_status_header_vm(
    scanner: dict[str, Any],
    metrics: dict[str, Any],
    strategy: dict[str, Any],
    *,
    now: float | None = None,
) -> StatusHeaderVM:
    """Build the status line content without depending on Qt widgets."""
    return StatusHeaderVM(
        headline=build_status_headline(scanner),
        progress_text=build_scan_progress_text(scanner, metrics, strategy, now=now),
        last_scan_text=build_last_scan_text(scanner),
    )


def build_status_headline(scanner: dict[str, Any]) -> str:
    status = str(scanner.get("status") or "idle").lower()
    progress = dict(scanner.get("progress") or {})
    if status == "scanning":
        total = max(0, int(progress.get("total") or 0))
        current = max(1, int(progress.get("current") or 0)) if total else int(progress.get("current") or 0)
        if total:
            return f"Hunting liquidity across live markets  ({current}/{total})"
        return "Hunting liquidity across live markets"
    if status == "running":
        return "Scanner armed and scanning for sweep setups"
    if status == "starting":
        return "Arming scanner services"
    if status == "stopping":
        return "Disarming scanner services"
    if status == "error":
        return "Scanner requires operator attention"
    if status == "stopped":
        return "Scanner disarmed"
    return "Scanner on standby"


def build_scan_progress_text(
    scanner: dict[str, Any],
    metrics: dict[str, Any],
    strategy: dict[str, Any],
    *,
    now: float | None = None,
) -> str:
    progress = dict(scanner.get("progress") or {})
    status = str(scanner.get("status") or "idle").lower()
    pieces: list[str] = []
    now_ts = time.time() if now is None else now
    if status == "scanning":
        total = max(0, int(progress.get("total") or 0))
        current = max(1, int(progress.get("current") or 0)) if total else int(progress.get("current") or 0)
        if total:
            pieces.append(f"Sweep pass {current}/{total}")
        current_symbol = progress.get("current_symbol")
        if current_symbol:
            pieces.append(f"Tracking {current_symbol}")
    else:
        scanned_symbols = int(metrics.get("scanned_symbols") or 0)
        total_symbols = int(metrics.get("total_symbols") or 0)
        if total_symbols:
            pieces.append(f"Market coverage {scanned_symbols}/{total_symbols}")
        next_scan_at = scanner.get("next_scan_at")
        if status == "running" and next_scan_at is not None:
            remaining = max(0, int(next_scan_at - now_ts))
            pieces.append(f"Next sweep check in {format_duration(remaining)}")
    pieces.append(f"Cadence {scanner.get('interval_sec', 0)}s")
    pieces.append(f"iFVG mode {strategy.get('ob_fvg_mode', 'medium')}")
    if status == "error" and scanner.get("last_error"):
        pieces.append(f"Error: {scanner['last_error']}")
    return "  |  ".join(piece for piece in pieces if piece)


def build_last_scan_text(scanner: dict[str, Any]) -> str:
    last_cycle = dict(scanner.get("last_cycle") or {})
    finished_at = last_cycle.get("finished_at")
    if finished_at:
        return f"Last sweep check {format_short_time(finished_at)}  |  {format_relative_age(finished_at)}"
    progress = dict(scanner.get("progress") or {})
    if progress.get("active") and progress.get("started_at"):
        return (
            f"Current hunt started {format_short_time(progress['started_at'])}"
            f"  |  {format_relative_age(progress['started_at'])}"
        )
    return "Last sweep check waiting for first cycle"


def render_activity_log(logs: list[dict[str, Any]], filter_key: str | None, query: str) -> str:
    """Render the telemetry log using the existing filtering rules."""
    from ui.presentation import log_matches_filter

    normalized_query = query.strip().lower()
    lines: list[str] = []
    for entry in logs:
        if not log_matches_filter(entry, filter_key):
            continue
        if normalized_query:
            search_blob = " ".join(
                str(entry.get(key) or "").lower()
                for key in ("symbol", "timeframe", "message", "phase", "reason")
            )
            if normalized_query not in search_blob:
                continue
        suffix = f" | reason={entry['reason']}" if entry.get("reason") else ""
        timestamp = str(entry.get("label") or format_timestamp(entry.get("timestamp")) or "-")
        lines.append(
            f"{timestamp} [{entry['level']}] {entry['symbol']} {entry['timeframe']} {entry['message']} | "
            f"phase={entry['phase']}{suffix}"
        )
    return "\n".join(lines[-150:])


def selected_payload_changed(
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
    selected_symbol: str | None,
) -> bool:
    if not selected_symbol:
        return True
    previous_rows = {str(item.get("symbol")): item for item in (previous_snapshot or {}).get("symbols", [])}
    current_rows = {str(item.get("symbol")): item for item in current_snapshot.get("symbols", [])}
    return previous_rows.get(selected_symbol) != current_rows.get(selected_symbol)
