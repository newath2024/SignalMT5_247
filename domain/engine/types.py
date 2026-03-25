"""Canonical typed containers for engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


__all__ = [
    "ConfirmedSignalResolution",
    "DisplayState",
    "HtfContextBundle",
    "ScoreState",
    "WatchCandidateResult",
    "WatchRefreshResult",
]
