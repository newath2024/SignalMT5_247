"""HTF context selection for the canonical engine pipeline."""

from __future__ import annotations

from typing import Any

from domain.context import detect_htf_context

from .reasoning import derive_htf_bias
from .types import HtfContextBundle


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


def build_htf_context(snapshot: dict[str, Any], htf_timeframes: list[str] | None = None) -> HtfContextBundle:
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


__all__ = ["build_htf_context", "directional_context_rank"]
