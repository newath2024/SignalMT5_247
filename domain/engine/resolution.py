"""Signal resolution helpers for the canonical engine pipeline."""

from __future__ import annotations

from typing import Any

from domain.confirmation import detect_confirmed_signal

from .reasoning import bias_label, format_context_label
from .types import ConfirmedSignalResolution


def resolve_confirmed_signal(
    snapshot: dict[str, Any],
    active_pool: list[dict[str, Any]],
    all_htf_zones: list[dict[str, Any]],
    contexts: dict[str, Any],
    primary_context: dict[str, Any] | None,
    htf_bias: str,
    unique_new_watches: list[dict[str, Any]],
    retained_watches: list[dict[str, Any]],
    rejections: list[dict[str, Any]],
) -> ConfirmedSignalResolution:
    confirmed_signal, confirm_rejection = detect_confirmed_signal(snapshot, active_pool, all_htf_zones)
    resolved_rejections = list(rejections)
    if confirm_rejection:
        resolved_rejections.append(
            {
                "symbol": snapshot["symbol"],
                "timeframe": "-",
                "bias": None,
                "phase": "signal",
                "reason": confirm_rejection,
            }
        )

    selected_watch = None
    if confirmed_signal is not None:
        for watch in active_pool:
            if watch["watch_key"] == confirmed_signal["watch_key"]:
                selected_watch = watch
                break
    if selected_watch is None and unique_new_watches:
        selected_watch = unique_new_watches[0]
    if selected_watch is None and retained_watches:
        selected_watch = retained_watches[0]

    selected_rejection = resolved_rejections[0] if resolved_rejections else None
    display_context = primary_context
    if selected_watch is not None and selected_watch.get("context"):
        display_context = selected_watch.get("context")
    elif confirmed_signal is not None and confirmed_signal.get("context"):
        display_context = confirmed_signal.get("context")
    elif selected_rejection is not None:
        rejection_bias = selected_rejection.get("bias")
        if rejection_bias in {"Long", "Short"}:
            display_context = contexts.get(rejection_bias) or primary_context

    htf_context = (
        confirmed_signal.get("htf_context")
        if confirmed_signal is not None
        else selected_watch.get("htf_context")
        if selected_watch is not None
        else format_context_label(display_context)
    )
    htf_bias_display = bias_label((display_context or {}).get("bias")) if display_context else htf_bias
    if htf_bias_display == "neutral":
        htf_bias_display = htf_bias

    return ConfirmedSignalResolution(
        confirmed_signal=confirmed_signal,
        rejections=resolved_rejections,
        selected_watch=selected_watch,
        selected_rejection=selected_rejection,
        display_context=display_context,
        htf_context=htf_context,
        htf_bias_display=htf_bias_display,
    )


__all__ = ["resolve_confirmed_signal"]
