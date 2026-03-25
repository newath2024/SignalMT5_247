"""HTF context selection for the active structure-only strategy."""

from __future__ import annotations

from .filters import determine_htf_structure, evaluate_htf_zone


def _tier_rank(evaluated):
    tier = str((evaluated.get("zone") or {}).get("tier") or evaluated.get("tier") or "C").upper()
    if tier == "A":
        return 3
    if tier == "B":
        return 2
    return 1


def _context_strength_rank(evaluated):
    strength = str(evaluated.get("context_strength") or "").lower()
    if strength == "strong":
        return 3
    if strength == "moderate":
        return 2
    if strength == "weak":
        return 1
    return 0


def _context_market_bias(evaluated):
    market_bias = evaluated.get("market_structure_bias")
    if market_bias in {"Long", "Short"}:
        return market_bias
    raw_bias = evaluated.get("bias")
    if raw_bias in {"Long", "Short"}:
        return raw_bias
    return None


def _interaction_index(evaluated):
    indices = [
        evaluated.get("tap_index"),
        evaluated.get("sweep_index"),
        evaluated.get("reclaim_index"),
        evaluated.get("mss_index"),
    ]
    resolved = [int(item) for item in indices if item is not None]
    if not resolved:
        return -1
    return max(resolved)


def _context_priority(evaluated):
    directional = _context_market_bias(evaluated) in {"Long", "Short"}
    rollover = bool(evaluated.get("rollover_active"))
    return (
        1 if directional else 0,
        _tier_rank(evaluated),
        _context_strength_rank(evaluated),
        1 if rollover else 0,
        float(evaluated.get("score") or 0.0),
        _interaction_index(evaluated),
    )


def _consider_context(best_by_bias, evaluated):
    if not evaluated.get("clear"):
        return

    bucket = evaluated.get("bias") or "Neutral"
    if bucket not in best_by_bias:
        bucket = "Neutral"

    current_best = best_by_bias[bucket]
    if current_best is None or _context_priority(evaluated) > _context_priority(current_best):
        best_by_bias[bucket] = evaluated


def select_htf_contexts(snapshot, zones):
    structure = determine_htf_structure(snapshot)
    best_by_bias = {"Long": None, "Short": None, "Neutral": None}

    for zone in zones:
        evaluated = evaluate_htf_zone(zone, snapshot, structure=structure)
        _consider_context(best_by_bias, evaluated)

    return best_by_bias
