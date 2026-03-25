"""Canonical setup scoring helpers for the trading pipeline."""

from __future__ import annotations


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def grade_from_score(score: float | None) -> str | None:
    if score is None or score <= 0:
        return None
    if score >= 8.6:
        return "A"
    if score >= 7.2:
        return "B"
    return "C"


def compute_setup_score(
    primary_context: dict | None,
    active_watch: dict | None,
    confirmed_signal: dict | None,
) -> tuple[float | None, str | None, dict[str, float]]:
    if confirmed_signal is not None:
        score = round(float(confirmed_signal.get("score") or 0.0), 1)
        components = {
            key: round(float(value), 2)
            for key, value in (confirmed_signal.get("score_components") or {}).items()
        }
        return score, grade_from_score(score), components

    if active_watch is not None:
        context = active_watch.get("context") or primary_context or {}
        ifvg = active_watch.get("ifvg") or {}
        ifvg_filter = active_watch.get("ifvg_filter") or {}
        reclaim = active_watch.get("reclaim") or {}
        displacement = active_watch.get("post_sweep_displacement") or {}
        components = {
            "htf_zone_quality": round(float(context.get("zone_quality") or 0.0), 2),
            "htf_reaction_clarity": round(float(context.get("reaction_clarity") or 0.0), 2),
            "liquidity_sweep_quality": round(float(active_watch.get("sweep_quality") or 0.0), 2),
            "mss_clarity": 0.0,
            "ifvg_quality": round(float(max(ifvg.get("quality") or 0.0, ifvg_filter.get("quality") or 0.0)), 2),
            "entry_location": round(float(ifvg.get("entry_quality") or 0.0), 2),
            "structural_stop_validity": 1.0 if active_watch.get("invalidation_price") is not None else 0.72,
            "rr": round(
                _clamp(0.35 + float(reclaim.get("quality") or 0.0) * 0.35 + float(displacement.get("quality") or 0.0) * 0.3),
                2,
            ),
        }
        score = round(sum(float(value) for value in components.values()), 1)
        return score, grade_from_score(score), components

    if primary_context is not None:
        components = {
            "htf_zone_quality": round(float(primary_context.get("zone_quality") or 0.0), 2),
            "htf_reaction_clarity": round(float(primary_context.get("reaction_clarity") or 0.0), 2),
            "liquidity_sweep_quality": 0.0,
            "mss_clarity": 0.0,
            "ifvg_quality": 0.0,
            "entry_location": 0.0,
            "structural_stop_validity": 0.0,
            "rr": 0.0,
        }
        score = round(sum(float(value) for value in components.values()), 1)
        return score, grade_from_score(score), components

    return None, None, {}


def format_score(score: float | None, grade: str | None) -> str:
    if score is None or grade is None:
        return "-"
    return f"{grade} ({score:.1f})"


__all__ = ["compute_setup_score", "format_score", "grade_from_score"]
