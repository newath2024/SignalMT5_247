from .filters import determine_htf_structure, evaluate_htf_zone


def _context_market_bias(evaluated):
    market_bias = evaluated.get("market_structure_bias")
    if market_bias in {"Long", "Short"}:
        return market_bias
    raw_bias = evaluated.get("bias")
    if raw_bias in {"Long", "Short"}:
        return raw_bias
    return None


def _context_priority(evaluated):
    zone = evaluated.get("zone") or {}
    is_liquidity = bool(zone.get("is_liquidity_level")) or bool(evaluated.get("is_liquidity_level"))
    directional = _context_market_bias(evaluated) in {"Long", "Short"}
    return (
        1 if directional else 0,
        0 if is_liquidity else 1,
        float(evaluated.get("score") or 0.0),
    )


def select_htf_contexts(snapshot, zones):
    structure = determine_htf_structure(snapshot)
    best_by_bias = {"Long": None, "Short": None, "Neutral": None}

    for zone in zones:
        evaluated = evaluate_htf_zone(zone, snapshot, structure=structure)
        if not evaluated["clear"]:
            continue

        bucket = evaluated.get("bias") or "Neutral"
        if bucket not in best_by_bias:
            bucket = "Neutral"

        current_best = best_by_bias[bucket]
        if current_best is None or _context_priority(evaluated) > _context_priority(current_best):
            best_by_bias[bucket] = evaluated

    return best_by_bias
