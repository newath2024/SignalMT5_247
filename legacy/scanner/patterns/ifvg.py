from ..config.ltf import (
    LTF_IFVG_INTERNAL_BASE_QUALITY,
    LTF_IFVG_INTERNAL_ENTRY_WEIGHT,
    LTF_IFVG_INTERNAL_MIN_ENTRY_QUALITY,
    LTF_IFVG_POST_BREAK_BARS,
    LTF_IFVG_SEARCH_BACK,
    LTF_IFVG_STRICT_BASE_QUALITY,
    LTF_IFVG_STRICT_ENTRY_WEIGHT,
    LTF_IFVG_ENTRY_DISTANCE_MIN_POINTS,
    LTF_IFVG_ENTRY_DISTANCE_RANGE_RATIO,
    LTF_IFVG_ENTRY_DISTANCE_WIDTH_RATIO,
    LTF_IFVG_ENTRY_MIN_QUALITY,
    LTF_IFVG_WIDTH_QUALITY_SCALE,
)
from ..utils import clamp, zone_distance


def find_first_touch_after_creation(rates, source_index, zone_low, zone_high):
    from .validators import find_first_touch_after_creation as _impl

    return _impl(rates, source_index, zone_low, zone_high)


def is_clean_ifvg_inversion(rates, bias, source_index, zone_low, zone_high, point):
    from .validators import is_clean_ifvg_inversion as _impl

    return _impl(rates, bias, source_index, zone_low, zone_high, point)


def is_valid_ifvg(candidate, rates, bias, confirmation_index, current_price, avg_range, point):
    from .validators import is_valid_ifvg as _impl

    return _impl(candidate, rates, bias, confirmation_index, current_price, avg_range, point)


def find_ifvg_candidates(rates, bias, sweep_index, mss_index):
    from .fvg import find_fvg_candidates

    strict_start = max(2, sweep_index - LTF_IFVG_SEARCH_BACK)
    strict_bias = "Short" if bias == "Long" else "Long"
    internal_bias = bias
    candidates = []

    def enrich_candidate(candidate, mode):
        # The middle candle of the 3-candle imbalance is the displacement candle
        # that actually creates the gap. We use its extreme for execution stops.
        origin_candle_index = candidate["source_index"] - 1
        return {
            **candidate,
            "mode": mode,
            "origin_candle_index": origin_candle_index,
            "origin_candle_high": float(rates["high"][origin_candle_index]),
            "origin_candle_low": float(rates["low"][origin_candle_index]),
        }

    for candidate in find_fvg_candidates(
        rates,
        bias=strict_bias,
        start_index=strict_start,
        end_index=mss_index,
    ):
        candidates.append(enrich_candidate(candidate, "strict"))

    for candidate in find_fvg_candidates(
        rates,
        bias=internal_bias,
        start_index=max(mss_index + 2, 2),
        end_index=len(rates) - 1,
    ):
        candidates.append(enrich_candidate(candidate, "internal"))

    return candidates


def _score_valid_ifvg(validation, avg_range, point):
    base = (
        LTF_IFVG_STRICT_BASE_QUALITY
        if validation["mode"] == "strict"
        else LTF_IFVG_INTERNAL_BASE_QUALITY
    )
    entry_weight = (
        LTF_IFVG_STRICT_ENTRY_WEIGHT
        if validation["mode"] == "strict"
        else LTF_IFVG_INTERNAL_ENTRY_WEIGHT
    )
    quality = (
        base
        + clamp(validation["width"] / max(avg_range, point)) * LTF_IFVG_WIDTH_QUALITY_SCALE
        + validation["entry_quality"] * entry_weight
    )
    return {
        "low": validation["low"],
        "high": validation["high"],
        "mode": validation["mode"],
        "quality": clamp(quality),
        "entry_quality": validation["entry_quality"],
        "source_index": validation["source_index"],
        "origin_candle_index": validation["origin_candle_index"],
        "origin_candle_high": validation["origin_candle_high"],
        "origin_candle_low": validation["origin_candle_low"],
        "entry_edge": validation["entry_edge"],
        "touch_index": validation["touch_index"],
        "post_break_confirmed": validation["post_break_confirmed"],
    }


def _flatten_merged_source_indices(zone):
    indices = []
    if zone.get("source_index") is not None:
        indices.append(int(zone["source_index"]))
    indices.extend(int(value) for value in zone.get("merged_source_indices") or [])
    return sorted(set(indices))


def _component_count(zone):
    return max(int(zone.get("component_count") or 0), 1)


def should_merge_ifvg_zones(left, right):
    if left is None or right is None:
        return False
    if str(left.get("mode") or "") != str(right.get("mode") or ""):
        return False
    left_indices = _flatten_merged_source_indices(left)
    right_indices = _flatten_merged_source_indices(right)
    if not left_indices or not right_indices:
        return False
    return min(right_indices) <= max(left_indices) + 1


def _ifvg_cluster_envelope(cluster):
    envelope = dict(cluster[0])
    envelope["merged_source_indices"] = sorted({index for zone in cluster for index in _flatten_merged_source_indices(zone)})
    envelope["source_index"] = min(envelope["merged_source_indices"]) if envelope["merged_source_indices"] else None
    return envelope


def _edge_component(zones, bias):
    if bias == "Long":
        return max(zones, key=lambda zone: (float(zone["high"]), int(zone.get("source_index") or 0)))
    return min(zones, key=lambda zone: (float(zone["low"]), int(zone.get("source_index") or 0)))


def _stop_component(zones, bias):
    if bias == "Long":
        return min(zones, key=lambda zone: (float(zone["origin_candle_low"]), int(zone.get("origin_candle_index") or 0)))
    return max(zones, key=lambda zone: (float(zone["origin_candle_high"]), -int(zone.get("origin_candle_index") or 0)))


def _entry_quality_for_zone(zone_low, zone_high, current_price, avg_range, point):
    width = max(float(zone_high) - float(zone_low), float(point), 1e-9)
    entry_distance = zone_distance(current_price, zone_low, zone_high)
    entry_quality = clamp(
        1.0
        - entry_distance
        / max(
            width * LTF_IFVG_ENTRY_DISTANCE_WIDTH_RATIO,
            avg_range * LTF_IFVG_ENTRY_DISTANCE_RANGE_RATIO,
            point * LTF_IFVG_ENTRY_DISTANCE_MIN_POINTS,
        )
    )
    return width, entry_distance, entry_quality


def _score_merged_ifvg(mode, zone_low, zone_high, current_price, avg_range, point):
    width, _entry_distance, entry_quality = _entry_quality_for_zone(zone_low, zone_high, current_price, avg_range, point)
    base = LTF_IFVG_STRICT_BASE_QUALITY if mode == "strict" else LTF_IFVG_INTERNAL_BASE_QUALITY
    entry_weight = LTF_IFVG_STRICT_ENTRY_WEIGHT if mode == "strict" else LTF_IFVG_INTERNAL_ENTRY_WEIGHT
    quality = base + clamp(width / max(avg_range, point, 1e-9)) * LTF_IFVG_WIDTH_QUALITY_SCALE + entry_quality * entry_weight
    return {
        "width": width,
        "entry_quality": entry_quality,
        "quality": clamp(quality),
    }


def _min_entry_quality(mode):
    return LTF_IFVG_ENTRY_MIN_QUALITY if mode == "strict" else LTF_IFVG_INTERNAL_MIN_ENTRY_QUALITY


def _merge_ifvg_cluster(zones, bias, current_price, avg_range, point):
    if len(zones) == 1:
        zone = dict(zones[0])
        zone["merged_source_indices"] = _flatten_merged_source_indices(zone)
        zone["component_count"] = _component_count(zone)
        return zone

    mode = str(zones[0]["mode"])
    merged_low = min(float(zone["low"]) for zone in zones)
    merged_high = max(float(zone["high"]) for zone in zones)
    edge_zone = _edge_component(zones, bias)
    stop_zone = _stop_component(zones, bias)
    scoring = _score_merged_ifvg(mode, merged_low, merged_high, current_price, avg_range, point)
    source_indices = sorted({index for zone in zones for index in _flatten_merged_source_indices(zone)})
    merged = dict(edge_zone)
    merged.update(
        {
            "low": merged_low,
            "high": merged_high,
            "quality": scoring["quality"],
            "entry_quality": scoring["entry_quality"],
            "source_index": min(source_indices) if source_indices else None,
            "entry_edge": merged_high if bias == "Long" else merged_low,
            "origin_candle_index": stop_zone["origin_candle_index"],
            "origin_candle_high": stop_zone["origin_candle_high"],
            "origin_candle_low": stop_zone["origin_candle_low"],
            "touch_index": edge_zone.get("touch_index"),
            "post_break_confirmed": bool(edge_zone.get("post_break_confirmed")),
            "min_entry_quality": _min_entry_quality(mode),
            "merged_source_indices": source_indices,
            "component_count": sum(_component_count(zone) for zone in zones),
        }
    )
    return merged


def merge_ifvg_zones(zones, bias, current_price, avg_range, point):
    if not zones:
        return []

    ordered = sorted(
        zones,
        key=lambda zone: (
            str(zone.get("mode") or ""),
            int(zone.get("source_index") or 0),
            float(zone.get("low") or 0.0),
            float(zone.get("high") or 0.0),
        ),
    )
    merged = []
    cluster = []

    for zone in ordered:
        candidate = dict(zone)
        if not cluster:
            cluster = [candidate]
            continue

        if should_merge_ifvg_zones(_ifvg_cluster_envelope(cluster), candidate):
            cluster.append(candidate)
            continue

        merged.append(_merge_ifvg_cluster(cluster, bias, current_price, avg_range, point))
        cluster = [candidate]

    if cluster:
        merged.append(_merge_ifvg_cluster(cluster, bias, current_price, avg_range, point))

    return merged


def find_ifvg_zone(rates, bias, sweep_index, mss_index, current_price, avg_range, point):
    strict_matches = []
    internal_matches = []

    for candidate in find_ifvg_candidates(rates, bias, sweep_index, mss_index):
        validation = is_valid_ifvg(
            candidate,
            rates,
            bias,
            mss_index,
            current_price,
            avg_range,
            point,
        )
        if not validation["valid"]:
            continue

        scored = _score_valid_ifvg(validation, avg_range, point)
        if scored["mode"] == "strict":
            strict_matches.append(scored)
        else:
            internal_matches.append(scored)

    strict_matches = [
        item
        for item in merge_ifvg_zones(strict_matches, bias, current_price, avg_range, point)
        if float(item.get("entry_quality") or 0.0) >= float(item.get("min_entry_quality") or LTF_IFVG_ENTRY_MIN_QUALITY)
    ]
    internal_matches = [
        item
        for item in merge_ifvg_zones(internal_matches, bias, current_price, avg_range, point)
        if float(item.get("entry_quality") or 0.0) >= float(item.get("min_entry_quality") or LTF_IFVG_INTERNAL_MIN_ENTRY_QUALITY)
    ]
    candidates = strict_matches or internal_matches
    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            1 if item["mode"] == "strict" else 0,
            item["entry_quality"],
            item["quality"],
            item["source_index"],
        ),
        reverse=True,
    )
    return candidates[0]
