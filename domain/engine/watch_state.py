"""Watch refresh and candidate merge helpers for the engine pipeline."""

from __future__ import annotations

from typing import Any

from domain.confirmation import detect_watch_candidates, watch_has_expired, watch_is_invalidated
from domain.context import refresh_htf_context
from domain.enums import SetupState

from .reasoning import describe_waiting_mss_reason, describe_watch_reason, direction_label
from .types import WatchCandidateResult, WatchRefreshResult


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


def refresh_active_watches(snapshot: dict[str, Any], active_watches: list[dict[str, Any]]) -> WatchRefreshResult:
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


__all__ = [
    "find_new_watch_candidates",
    "prepare_retained_watch",
    "refresh_active_watches",
    "waiting_for_from_watch",
]
