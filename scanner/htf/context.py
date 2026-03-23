from .filters import determine_htf_structure, evaluate_htf_zone
from .liquidity import is_liquidity_level, liquidity_level_side, liquidity_level_value


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
    rollover = bool(evaluated.get("rollover_active"))
    return (
        1 if directional else 0,
        1 if rollover else 0,
        0 if is_liquidity else 1,
        float(evaluated.get("score") or 0.0),
        _interaction_index(evaluated),
    )


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


def _directional_alignment(structure, bias):
    trend = (structure or {}).get("trend", "Range")
    if trend == "Bullish":
        return "aligned" if bias == "Long" else "countertrend"
    if trend == "Bearish":
        return "aligned" if bias == "Short" else "countertrend"
    return "range"


def _rollover_interaction_bonus(evaluated):
    state = str(evaluated.get("liquidity_interaction_state") or "")
    if state == "swept_and_reclaimed":
        return 0.24
    if state == "swept":
        return 0.18
    if state == "tapped":
        return 0.1
    return 0.0


def _rollover_session_bonus(evaluated):
    zone = evaluated.get("zone") or {}
    reference_key = str(zone.get("reference_key") or "")
    if reference_key in {"ASH", "ASL", "LOH", "LOL"}:
        return 0.08
    return 0.0


def _liquidity_contexts(evaluated_items):
    return [item for item in evaluated_items if is_liquidity_level(item.get("zone"))]


def _build_rollover_context(target, origin, direction, structure):
    promoted = dict(target)
    existing_reason = str(promoted.get("structure_confirmation_reason") or "").strip()
    rollover_reason = f"rollover from {origin['zone']['label']} to {target['zone']['label']}"
    promoted["bias"] = direction
    promoted["market_structure_bias"] = direction
    promoted["trend_alignment"] = _directional_alignment(structure, direction)
    promoted["clear"] = True
    promoted["rollover_active"] = True
    promoted["rollover_from_label"] = origin["zone"]["label"]
    promoted["rollover_to_label"] = target["zone"]["label"]
    promoted["rollover_reason"] = rollover_reason
    promoted["score"] = float(promoted.get("score") or 0.0) + 0.12 + _rollover_interaction_bonus(target) + _rollover_session_bonus(target)
    promoted["structure_confirmation_reason"] = (
        f"{existing_reason} | {rollover_reason}" if existing_reason else rollover_reason
    )
    liquidity_debug = str(promoted.get("liquidity_debug") or "").strip()
    extra_debug = f"rollover_from={origin['zone']['label']}; rollover_origin_state={origin.get('liquidity_interaction_state')}"
    promoted["liquidity_debug"] = f"{liquidity_debug}; {extra_debug}" if liquidity_debug else extra_debug
    return promoted


def _find_rollover_contexts(evaluated_items, structure):
    liquidity_items = _liquidity_contexts(evaluated_items)
    rollovers = []
    for direction, target_side, origin_side in (("Short", "high", "low"), ("Long", "low", "high")):
        origins = [
            item
            for item in liquidity_items
            if liquidity_level_side(item.get("zone")) == origin_side
            and str(item.get("liquidity_interaction_state") or "") == "swept_and_reclaimed"
        ]
        targets = [
            item
            for item in liquidity_items
            if liquidity_level_side(item.get("zone")) == target_side
            and str(item.get("liquidity_interaction_state") or "") in {"tapped", "swept", "swept_and_reclaimed"}
        ]
        if not origins or not targets:
            continue

        best_origin = max(
            origins,
            key=lambda item: (
                _interaction_index(item),
                float(item.get("score") or 0.0),
            ),
        )
        origin_index = _interaction_index(best_origin)
        eligible_targets = [item for item in targets if _interaction_index(item) >= origin_index]
        if not eligible_targets:
            eligible_targets = targets

        def _target_rank(item):
            level = liquidity_level_value(item.get("zone"))
            if level is None:
                extreme_value = float("-inf")
            else:
                extreme_value = float(level) if target_side == "high" else -float(level)
            return (
                _rollover_interaction_bonus(item),
                _rollover_session_bonus(item),
                _interaction_index(item),
                extreme_value,
                float(item.get("distance_score") or 0.0),
                float(item.get("score") or 0.0),
            )

        best_target = max(
            eligible_targets,
            key=_target_rank,
        )
        rollovers.append(_build_rollover_context(best_target, best_origin, direction, structure))

    return rollovers


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
    evaluated_items = []

    for zone in zones:
        evaluated = evaluate_htf_zone(zone, snapshot, structure=structure)
        evaluated_items.append(evaluated)
        _consider_context(best_by_bias, evaluated)

    for rollover in _find_rollover_contexts(evaluated_items, structure):
        _consider_context(best_by_bias, rollover)

    return best_by_bias
