"""Canonical trading pipeline orchestration package.

Public API is re-exported here, while internal engine logic is intentionally
split across smaller modules to avoid a catch-all namespace.
"""

from .context import build_htf_context
from .display import derive_display_state, phase_for_watch_status
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
from .strategy import StrategyDecision, StrategyEngine
from .watch_state import find_new_watch_candidates, refresh_active_watches

__all__ = [
    "ConfirmedSignalResolution",
    "DisplayState",
    "HtfContextBundle",
    "ScoreState",
    "StrategyDecision",
    "StrategyEngine",
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
