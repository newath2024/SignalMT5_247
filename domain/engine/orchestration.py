"""Top-level orchestration helpers for the canonical engine pipeline."""

from __future__ import annotations

from typing import Any

from domain.engine.types import ScoreState

from .reasoning import build_detail_payload


def score_setup(
    display_context: dict[str, Any] | None,
    selected_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
) -> ScoreState:
    from domain.scoring import compute_setup_score

    score, grade, score_components = compute_setup_score(display_context, selected_watch, confirmed_signal)
    return ScoreState(score=score, grade=grade, score_components=score_components)


def build_strategy_decision(
    *,
    snapshot: dict[str, Any],
    display_state,
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
    detail = build_detail_payload(
        display_state.state,
        htf_bias_display,
        display_context,
        selected_watch,
        confirmed_signal,
        selected_rejection,
        score_state.score,
        score_state.grade,
        score_state.score_components,
        snapshot=snapshot,
    )
    focus_watch = confirmed_signal if confirmed_signal is not None else selected_watch
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
        "focus_watch": focus_watch,
        "primary_context": primary_context,
        "detail": detail,
        "active_watches": active_pool,
        "new_watches": unique_new_watches,
        "removed_watches": removed_watches,
        "rejections": rejections,
        "confirmed_signal": confirmed_signal,
        "current_price": snapshot.get("current_price"),
        "broker_now": snapshot["broker_now"].isoformat(timespec="seconds") if snapshot.get("broker_now") else None,
    }


__all__ = ["build_strategy_decision", "score_setup"]
