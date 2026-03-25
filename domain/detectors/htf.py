from legacy.bridges.detection import build_htf_zones, evaluate_htf_zone, select_htf_contexts


def detect_htf_context(snapshot, allowed_timeframes: list[str] | None = None):
    zones = build_htf_zones(snapshot)
    if allowed_timeframes:
        allowed = {str(item).upper() for item in allowed_timeframes}
        zones = [zone for zone in zones if str(zone.get("timeframe") or "").upper() in allowed]
    contexts = select_htf_contexts(snapshot, zones)
    return zones, contexts


def refresh_htf_context(snapshot, zone):
    return evaluate_htf_zone(zone, snapshot)
