"""Compatibility-facing pipeline facade for the canonical engine package.

Public callers may continue importing from ``domain.engine.pipeline`` while the
actual source of truth is split across smaller engine modules.
"""

from .context import build_htf_context, directional_context_rank
from .display import derive_display_state, phase_for_rejection, phase_for_watch_status
from .orchestration import build_strategy_decision, score_setup
from .resolution import resolve_confirmed_signal
from .types import (
    ConfirmedSignalResolution,
    DisplayState,
    HtfContextBundle,
    ScoreState,
    WatchCandidateResult,
    WatchRefreshResult,
)
from .watch_state import (
    find_new_watch_candidates,
    prepare_retained_watch,
    refresh_active_watches,
    waiting_for_from_watch,
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
    "directional_context_rank",
    "find_new_watch_candidates",
    "phase_for_rejection",
    "phase_for_watch_status",
    "prepare_retained_watch",
    "refresh_active_watches",
    "resolve_confirmed_signal",
    "score_setup",
    "waiting_for_from_watch",
]
