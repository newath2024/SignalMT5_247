"""Compatibility shim for strategy pipeline helpers.

Canonical implementation lives in ``domain.engine.pipeline``.
Safe to remove after import migration.
"""

from domain.engine.pipeline import (
    ConfirmedSignalResolution,
    DisplayState,
    HtfContextBundle,
    ScoreState,
    WatchCandidateResult,
    WatchRefreshResult,
    build_htf_context,
    build_strategy_decision,
    derive_display_state,
    find_new_watch_candidates,
    phase_for_watch_status,
    refresh_active_watches,
    resolve_confirmed_signal,
    score_setup,
)

__all__ = [
    "ConfirmedSignalResolution",
    "DisplayState",
    "HtfContextBundle",
    "ScoreState",
    "WatchCandidateResult",
    "WatchRefreshResult",
    "build_htf_context",
    "build_strategy_decision",
    "derive_display_state",
    "find_new_watch_candidates",
    "phase_for_watch_status",
    "refresh_active_watches",
    "resolve_confirmed_signal",
    "score_setup",
]
