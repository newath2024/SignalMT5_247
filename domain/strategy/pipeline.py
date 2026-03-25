"""Pure strategy pipeline helpers.

Canonical strategy orchestration lives here; ``StrategyEngine`` is now a thin
runtime wrapper around these functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.detectors.htf import detect_htf_context, refresh_htf_context
from domain.detectors.ltf import detect_confirmed_signal, detect_watch_candidates, watch_has_expired, watch_is_invalidated
from domain.enums import SetupPhase, SetupState

from .reasoning import (
    bias_label,
    build_detail_payload,
    compute_setup_score,
    derive_htf_bias,
    describe_context_wait,
    describe_rejection,
    describe_waiting_mss_reason,
    describe_watch_reason,
    direction_label,
    format_context_label,
)


@dataclass(frozen=True)
class HtfContextBundle:
    all_htf_zones: list[dict[str, Any]]
    contexts: dict[str, Any]
    htf_bias: str
    primary_context: dict[str, Any] | None
    best_directional_context: dict[str, Any] | None
    active_htf: str | None


@dataclass(frozen=True)
class WatchRefreshResult:
    retained_watches: list[dict[str, Any]]
    removed_watches: list[dict[str, Any]]


@dataclass(frozen=True)
class WatchCandidateResult:
    new_watches: list[dict[str, Any]]
    unique_new_watches: list[dict[str, Any]]
    rejections: list[dict[str, Any]]
    active_pool: list[dict[str, Any]]


@dataclass(frozen=True)
class ConfirmedSignalResolution:
    confirmed_signal: dict[str, Any] | None
    rejections: list[dict[str, Any]]
    selected_watch: dict[str, Any] | None
    selected_rejection: dict[str, Any] | None
    display_context: dict[str, Any] | None
    htf_context: str
    htf_bias_display: str


@dataclass(frozen=True)
class DisplayState:
    state: str
    phase: str
    reason: str
    timeframe: str
    waiting_for: str
    active_watch_id: str | None


@dataclass(frozen=True)
class ScoreState:
    score: float | None
    grade: str | None
    score_components: dict[str, Any]


def directional_context_rank(item: dict[str, Any] | None) -> tuple[int, int, int, float]:
    zone = (item or {}).get("zone") or {}
    tier = str(zone.get("tier") or (item or {}).get("tier") or "C").upper()
    tier_rank = 3 if tier == "A" else 2 if tier == "B" else 1
    strength = str((item or {}).get("context_strength") or zone.get("context_strength") or "").lower()
    strength_rank = 3 if strength == "strong" else 2 if strength == "moderate" else 1 if strength == "weak" else 0
    return (
        1 if (item or {}).get("rollover_active") else 0,
        tier_rank,
        strength_rank,
        float((item or {}).get("score") or 0.0),
    )


def phase_for_watch_status(status: str | None) -> str:
    status = str(status or "").lower()
    if status in {SetupState.ARMED.value, SetupState.TRIGGERED.value}:
        return SetupPhase.READY.value
    if status == SetupState.AWAITING_IFVG.value:
        return SetupPhase.WAITING_IFVG.value
    if status in {SetupState.SWEEP_DETECTED.value, SetupState.WAITING_MSS.value}:
        return SetupPhase.WAITING_MSS.value
    return SetupPhase.NARRATIVE.value


def waiting_for_from_watch(watch: dict[str, Any]) -> str:
    status = str(watch.get("status") or "").lower()
    if status in {
        SetupState.DEGRADED.value,
        SetupState.INVALIDATED.value,
        SetupState.TWO_SIDED_LIQUIDITY_TAKEN.value,
        SetupState.AMBIGUOUS.value,
    }:
        return "-"
    if status == SetupState.AWAITING_IFVG.value:
        return "strict iFVG"
    if status in {SetupState.ARMED.value, SetupState.TRIGGERED.value}:
        return "trigger"
    return "MSS"


def prepare_retained_watch(snapshot: dict[str, Any], watch_setup: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Refresh one persisted watch against the latest HTF/LTF data."""
    refreshed_context = refresh_htf_context(snapshot, watch_setup["htf_zone"])
    if watch_has_expired(snapshot, watch_setup):
        removed = dict(watch_setup)
        removed["removal_reason"] = "expired"
        return None, removed
    if watch_is_invalidated(snapshot, watch_setup, refreshed_context):
        removed = dict(watch_setup)
        removed["removal_reason"] = "entry invalidated"
        return None, removed

    updated = dict(watch_setup)
    updated["context"] = refreshed_context
    if updated.get("status") not in {"confirmed", "cooldown", SetupState.ARMED.value}:
        updated["status"] = updated.get("narrative_state") or updated.get("status") or SetupState.WAITING_MSS.value
    updated["direction"] = updated.get("direction") or direction_label(updated.get("bias"))
    updated["waiting_for"] = waiting_for_from_watch(updated)
    updated["ltf_sweep_status"] = updated.get("ltf_sweep_status") or "narrative active"
    if updated.get("ifvg"):
        updated["zone_top"] = updated.get("zone_top") or float(updated["ifvg"]["high"])
        updated["zone_bottom"] = updated.get("zone_bottom") or float(updated["ifvg"]["low"])
    updated["status_reason"] = updated.get("status_reason") or describe_waiting_mss_reason(updated)
    return updated, None


def phase_for_rejection(rejection: dict[str, Any]) -> str:
    phase = str(rejection.get("phase") or "").lower()
    if phase == "signal":
        return SetupPhase.READY.value
    if phase == "watch":
        return SetupPhase.IFVG_VALIDATION.value
    return SetupPhase.HTF_CONTEXT.value


def build_htf_context(snapshot: dict[str, Any], htf_timeframes: list[str] | None = None) -> HtfContextBundle:
    """Resolve HTF zones, selected contexts, and bias for the current snapshot."""
    all_htf_zones, contexts = detect_htf_context(snapshot, allowed_timeframes=htf_timeframes)
    htf_bias, primary_context = derive_htf_bias(contexts)
    directional_contexts = [contexts.get("Long"), contexts.get("Short")]
    directional_contexts = [item for item in directional_contexts if item is not None]
    best_directional_context = max(directional_contexts, key=directional_context_rank) if directional_contexts else None
    return HtfContextBundle(
        all_htf_zones=all_htf_zones,
        contexts=contexts,
        htf_bias=htf_bias,
        primary_context=primary_context,
        best_directional_context=best_directional_context,
        active_htf=str((primary_context or {}).get("zone", {}).get("timeframe") or "") or None,
    )


def refresh_active_watches(snapshot: dict[str, Any], active_watches: list[dict[str, Any]]) -> WatchRefreshResult:
    """Refresh persisted watches and classify removals."""
    retained_watches: list[dict[str, Any]] = []
    removed_watches: list[dict[str, Any]] = []
    for watch_setup in active_watches:
        retained, removed = prepare_retained_watch(snapshot, watch_setup)
        if retained is not None:
            retained_watches.append(retained)
        if removed is not None:
            removed_watches.append(removed)
    return WatchRefreshResult(retained_watches=retained_watches, removed_watches=removed_watches)


def find_new_watch_candidates(
    snapshot: dict[str, Any],
    contexts: dict[str, Any],
    active_htf: str,
    confirmation_timeframes: list[str],
    retained_watches: list[dict[str, Any]],
) -> WatchCandidateResult:
    """Find new watch candidates and merge them into the active pool."""
    new_watches, rejections = detect_watch_candidates(snapshot, contexts, confirmation_timeframes)
    retained_by_key = {item["watch_key"]: item for item in retained_watches}
    unique_new_watches: list[dict[str, Any]] = []
    for watch in new_watches:
        watch["active_htf"] = active_htf
        watch["confirmation_timeframes"] = list(confirmation_timeframes)
        watch["status"] = watch.get("status") or watch.get("narrative_state") or SetupState.WAITING_MSS.value
        watch["direction"] = watch.get("direction") or direction_label(watch.get("bias"))
        watch["waiting_for"] = waiting_for_from_watch(watch)
        watch["ltf_sweep_status"] = watch.get("ltf_sweep_status") or "narrative active"
        watch["status_reason"] = watch.get("status_reason") or describe_watch_reason(watch)
        if watch["watch_key"] in retained_by_key:
            retained_by_key[watch["watch_key"]] = watch
            continue
        unique_new_watches.append(watch)

    retained = list(retained_by_key.values())
    return WatchCandidateResult(
        new_watches=new_watches,
        unique_new_watches=unique_new_watches,
        rejections=rejections,
        active_pool=retained + unique_new_watches,
    )


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
    """Resolve confirmed signals and select the display context/watch."""
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


def derive_display_state(
    *,
    confirmed_signal: dict[str, Any] | None,
    unique_new_watches: list[dict[str, Any]],
    retained_watches: list[dict[str, Any]],
    selected_rejection: dict[str, Any] | None,
    best_directional_context: dict[str, Any] | None,
    primary_context: dict[str, Any] | None,
) -> DisplayState:
    """Select the user-visible state/phase/reason for the symbol."""
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
        if selected_retained.get("status") == SetupState.COOLDOWN.value:
            return DisplayState(
                state=SetupState.COOLDOWN.value,
                phase=SetupPhase.ALERT_SENT.value,
                reason=selected_retained.get("status_reason") or "cooldown: prior alert still active",
                timeframe=selected_retained["timeframe"],
                waiting_for="cooldown",
                active_watch_id=selected_retained["watch_key"],
            )
        if selected_retained.get("status") in {SetupState.CONFIRMED.value, SetupState.TRIGGERED.value}:
            return DisplayState(
                state=SetupState.TRIGGERED.value,
                phase=SetupPhase.READY.value,
                reason=selected_retained.get("status_reason") or "triggered: signal already recorded",
                timeframe=selected_retained["timeframe"],
                waiting_for="operator review",
                active_watch_id=selected_retained["watch_key"],
            )
        return DisplayState(
            state=selected_retained.get("status") or SetupState.WAITING_MSS.value,
            phase=phase_for_watch_status(selected_retained.get("status")),
            reason=selected_retained.get("status_reason") or describe_waiting_mss_reason(selected_retained),
            timeframe=selected_retained["timeframe"],
            waiting_for=waiting_for_from_watch(selected_retained),
            active_watch_id=selected_retained["watch_key"],
        )
    if selected_rejection is not None:
        return DisplayState(
            state=SetupState.REJECTED.value,
            phase=phase_for_rejection(selected_rejection),
            reason=describe_rejection(selected_rejection["reason"]),
            timeframe=selected_rejection["timeframe"],
            waiting_for="-",
            active_watch_id=None,
        )
    if best_directional_context is not None:
        return DisplayState(
            state=SetupState.AWAITING_LTF_SWEEP.value,
            phase=SetupPhase.LTF_SWEEP.value,
            reason=describe_context_wait(best_directional_context),
            timeframe=best_directional_context.get("zone", {}).get("timeframe", "-"),
            waiting_for="sweep",
            active_watch_id=None,
        )
    if primary_context is not None:
        zone = primary_context.get("zone", {}) or {}
        tier = str(zone.get("tier") or primary_context.get("tier") or "C").upper()
        context_strength = str(primary_context.get("context_strength") or zone.get("context_strength") or "weak").lower()
        if tier == "C":
            state = SetupState.NO_STRUCTURAL_BACKING.value if bool(primary_context.get("no_structural_backing")) else SetupState.HTF_WEAK_CONTEXT.value
        elif context_strength == "weak":
            state = SetupState.HTF_WEAK_CONTEXT.value
        else:
            state = SetupState.HTF_CONTEXT_FOUND.value
        return DisplayState(
            state=state,
            phase=SetupPhase.HTF_CONTEXT.value,
            reason=describe_context_wait(primary_context),
            timeframe=primary_context.get("zone", {}).get("timeframe", "-"),
            waiting_for="HTF confirmation",
            active_watch_id=None,
        )
    return DisplayState(
        state=SetupState.IDLE.value,
        phase=SetupPhase.HTF_CONTEXT.value,
        reason="waiting: HTF context",
        timeframe="-",
        waiting_for="HTF context",
        active_watch_id=None,
    )


def score_setup(
    display_context: dict[str, Any] | None,
    selected_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
) -> ScoreState:
    """Score the chosen setup using the existing scoring model."""
    score, grade, score_components = compute_setup_score(display_context, selected_watch, confirmed_signal)
    return ScoreState(score=score, grade=grade, score_components=score_components)


def build_strategy_decision(
    *,
    snapshot: dict[str, Any],
    display_state: DisplayState,
    htf_bias_display: str,
    htf_context: str,
    score_state: ScoreState,
    display_context: dict[str, Any] | None,
    selected_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
    selected_rejection: dict[str, Any] | None,
    primary_context: dict[str, Any] | None,
    active_pool: list[dict[str, Any]],
    unique_new_watches: list[dict[str, Any]],
    removed_watches: list[dict[str, Any]],
    rejections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the final ``StrategyDecision`` constructor payload."""
    detail = build_detail_payload(
        state=display_state.state,
        htf_bias=htf_bias_display,
        primary_context=display_context,
        active_watch=selected_watch,
        confirmed_signal=confirmed_signal,
        rejection=selected_rejection,
        score=score_state.score,
        grade=score_state.grade,
        score_components=score_state.score_components,
        snapshot=snapshot,
    )
    return {
        "symbol": snapshot["symbol"],
        "state": display_state.state,
        "phase": display_state.phase,
        "reason": display_state.reason,
        "htf_bias": htf_bias_display,
        "timeframe": display_state.timeframe,
        "htf_context": htf_context,
        "waiting_for": display_state.waiting_for,
        "score": score_state.score,
        "grade": score_state.grade,
        "score_components": score_state.score_components,
        "active_watch_id": display_state.active_watch_id,
        "focus_watch": selected_watch,
        "primary_context": primary_context,
        "detail": detail,
        "active_watches": active_pool,
        "new_watches": unique_new_watches,
        "removed_watches": removed_watches,
        "rejections": rejections,
        "confirmed_signal": confirmed_signal,
        "current_price": float(snapshot["current_price"]),
        "broker_now": snapshot["broker_now"].isoformat(timespec="seconds"),
    }
