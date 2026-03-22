from .filters import determine_htf_structure, evaluate_htf_zone


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
        if current_best is None or evaluated["score"] > current_best["score"]:
            best_by_bias[bucket] = evaluated

    return best_by_bias
