"""Display-state derivation for the canonical engine pipeline."""

from __future__ import annotations

from typing import Any

from domain.enums import SetupPhase, SetupState

from .reasoning import describe_context_wait, describe_rejection, describe_watch_reason
from .types import DisplayState
from .watch_state import waiting_for_from_watch


def phase_for_watch_status(status: str | None) -> str:
    status = str(status or "").lower()
    if status in {SetupState.ARMED.value, SetupState.TRIGGERED.value}:
        return SetupPhase.READY.value
    if status == SetupState.AWAITING_IFVG.value:
        return SetupPhase.WAITING_IFVG.value
    if status in {SetupState.SWEEP_DETECTED.value, SetupState.WAITING_MSS.value}:
        return SetupPhase.WAITING_MSS.value
    return SetupPhase.NARRATIVE.value


def phase_for_rejection(rejection: dict[str, Any]) -> str:
    phase = str(rejection.get("phase") or "").lower()
    if phase == "signal":
        return SetupPhase.READY.value
    if phase == "watch":
        return SetupPhase.IFVG_VALIDATION.value
    return SetupPhase.HTF_CONTEXT.value


def derive_display_state(
    *,
    confirmed_signal: dict[str, Any] | None,
    unique_new_watches: list[dict[str, Any]],
    retained_watches: list[dict[str, Any]],
    selected_rejection: dict[str, Any] | None,
    best_directional_context: dict[str, Any] | None,
    primary_context: dict[str, Any] | None,
) -> DisplayState:
    if confirmed_signal is not None:
        return DisplayState(
            state=SetupState.TRIGGERED.value,
            phase=SetupPhase.READY.value,
            reason="triggered: narrative ready with MSS + strict iFVG",
            timeframe=confirmed_signal["timeframe"],
            waiting_for="entry",
            active_watch_id=confirmed_signal["watch_key"],
        )
    if unique_new_watches:
        focus = unique_new_watches[0]
        return DisplayState(
            state=focus.get("status") or SetupState.WAITING_MSS.value,
            phase=phase_for_watch_status(focus.get("status")),
            reason=focus.get("status_reason") or describe_watch_reason(focus),
            timeframe=focus["timeframe"],
            waiting_for=waiting_for_from_watch(focus),
            active_watch_id=focus["watch_key"],
        )
    if retained_watches:
        selected_retained = retained_watches[0]
        return DisplayState(
            state=selected_retained.get("status") or SetupState.WAITING_MSS.value,
            phase=phase_for_watch_status(selected_retained.get("status")),
            reason=selected_retained.get("status_reason") or describe_watch_reason(selected_retained),
            timeframe=selected_retained["timeframe"],
            waiting_for=waiting_for_from_watch(selected_retained),
            active_watch_id=selected_retained["watch_key"],
        )
    if selected_rejection is not None:
        return DisplayState(
            state=SetupState.REJECTED.value,
            phase=phase_for_rejection(selected_rejection),
            reason=describe_rejection(selected_rejection.get("reason")),
            timeframe=str(selected_rejection.get("timeframe") or "-"),
            waiting_for="-",
            active_watch_id=None,
        )
    if best_directional_context is not None or primary_context is not None:
        focus_context = best_directional_context or primary_context
        return DisplayState(
            state=SetupState.CONTEXT_FOUND.value,
            phase=SetupPhase.HTF_CONTEXT.value,
            reason=describe_context_wait(focus_context),
            timeframe=str(((focus_context or {}).get("zone") or {}).get("timeframe") or "-"),
            waiting_for="LTF sweep",
            active_watch_id=None,
        )
    return DisplayState(
        state=SetupState.NO_SETUP.value,
        phase=SetupPhase.IDLE.value,
        reason="waiting: structure not aligned",
        timeframe="-",
        waiting_for="HTF context",
        active_watch_id=None,
    )


__all__ = ["derive_display_state", "phase_for_rejection", "phase_for_watch_status"]
