from legacy.bridges.detection import build_htf_zones, evaluate_htf_zone, select_htf_contexts


def detect_htf_context(snapshot):
    zones = build_htf_zones(snapshot)
    contexts = select_htf_contexts(snapshot, zones)
    return zones, contexts


def refresh_htf_context(snapshot, zone):
    return evaluate_htf_zone(zone, snapshot)
