from ..config.htf import (
    HTF_FVG_CLASS_BONUS,
    HTF_FVG_MAX_ZONES,
    HTF_FVG_MERGE_TOLERANCE_AVG_RANGE_RATIO,
    HTF_FVG_MERGE_TOLERANCE_POINTS,
    HTF_FVG_MERGE_TOLERANCE_ZONE_WIDTH_RATIO,
    HTF_FVG_MIN_BARS,
    HTF_FVG_LOOKBACK,
    HTF_FVG_MIN_POINTS,
    HTF_FVG_QUALITY_BASE,
    HTF_FVG_QUALITY_DIVISOR,
    HTF_FVG_QUALITY_SCALE,
    HTF_FVG_TIMEFRAME_BONUS,
    HTF_FVG_TRADABLE_MIN_QUALITY,
)
from .fvg_assessment import assess_fvg_candidate
from .swings import build_swing_structure
from ..utils import clamp, zone_width


def find_fvg_candidates(rates, lookback=HTF_FVG_LOOKBACK, bias=None, start_index=None, end_index=None):
    if rates is None or len(rates) < HTF_FVG_MIN_BARS:
        return []

    highs = rates["high"]
    lows = rates["low"]
    start = max(lookback, start_index or lookback)
    end = min(len(rates) - 1, end_index if end_index is not None else len(rates) - 1)
    candidates = []

    for index in range(start, end + 1):
        bullish_gap = float(lows[index] - highs[index - lookback])
        bearish_gap = float(lows[index - lookback] - highs[index])

        if bias in (None, "Long") and bullish_gap > 0:
            candidates.append(
                {
                    "geometric_fvg": True,
                    "bias": "Long",
                    "start_index": index - lookback,
                    "middle_index": index - 1,
                    "source_index": index,
                    "low": float(highs[index - lookback]),
                    "high": float(lows[index]),
                    "width": bullish_gap,
                }
            )
        if bias in (None, "Short") and bearish_gap > 0:
            candidates.append(
                {
                    "geometric_fvg": True,
                    "bias": "Short",
                    "start_index": index - lookback,
                    "middle_index": index - 1,
                    "source_index": index,
                    "low": float(highs[index]),
                    "high": float(lows[index - lookback]),
                    "width": bearish_gap,
                }
            )

    return candidates


def has_impulse_fvg(rates, bias, avg_range, point, start_index, end_index):
    swings = build_swing_structure(rates, avg_range)
    candidates = find_fvg_candidates(
        rates,
        bias=bias,
        start_index=start_index,
        end_index=end_index,
    )
    for candidate in candidates:
        validation = assess_fvg_candidate(candidate, rates, "H1", avg_range, point, swings=swings)
        if validation["tradable"] and validation["formed_in_displacement"] and validation["follow_through_confirmed"]:
            return True
    return False


def _fvg_merge_tolerance(point, avg_range, left=None, right=None):
    width_tolerance = 0.0
    if left is not None and right is not None:
        width_tolerance = max(zone_width(left), zone_width(right)) * HTF_FVG_MERGE_TOLERANCE_ZONE_WIDTH_RATIO
    return max(
        float(point) * HTF_FVG_MERGE_TOLERANCE_POINTS,
        float(avg_range) * HTF_FVG_MERGE_TOLERANCE_AVG_RANGE_RATIO,
        width_tolerance,
    )


def should_merge_fvg_zones(left, right, point, avg_range):
    if left is None or right is None:
        return False
    if left.get("bias") != right.get("bias"):
        return False
    if str(left.get("timeframe") or "").upper() != str(right.get("timeframe") or "").upper():
        return False
    left_indices = _flatten_merged_source_indices(left)
    right_indices = _flatten_merged_source_indices(right)
    if left_indices and right_indices and min(right_indices) <= max(left_indices) + 1:
        return True

    left_low = float(min(left["low"], left["high"]))
    left_high = float(max(left["low"], left["high"]))
    right_low = float(min(right["low"], right["high"]))
    right_high = float(max(right["low"], right["high"]))
    overlap = right_low <= left_high and right_high >= left_low
    if overlap:
        return True

    gap = max(right_low - left_high, left_low - right_high, 0.0)
    return gap <= _fvg_merge_tolerance(point, avg_range, left=left, right=right)


def _flatten_merged_source_indices(zone):
    indices = []
    if zone.get("source_index") is not None:
        indices.append(int(zone["source_index"]))
    indices.extend(int(value) for value in zone.get("merged_source_indices") or [])
    return sorted(set(indices))


def _component_count(zone):
    return max(int(zone.get("component_count") or 0), 1)


def _max_component(zones, key, default=0.0):
    values = []
    for zone in zones:
        payload = zone.get("quality_components") or {}
        if key in payload:
            values.append(float(payload[key]))
    return max(values) if values else float(default)


def _max_penalty(zones, key):
    values = []
    for zone in zones:
        payload = zone.get("quality_penalties") or {}
        if key in payload:
            values.append(float(payload[key]))
    return max(values) if values else 0.0


def _select_anchor_zone(zones):
    return max(
        zones,
        key=lambda zone: (
            float(zone.get("quality") or 0.0),
            1 if zone.get("tradable") else 0,
            -(int(zone.get("source_index") or 0)),
        ),
    )


def _combine_strength(zones, field_name, ranking):
    best = None
    best_rank = -1
    for zone in zones:
        value = zone.get(field_name)
        rank = ranking.get(value, -1)
        if rank > best_rank:
            best = value
            best_rank = rank
    return best


def _combine_class(zones):
    best = None
    best_bonus = float("-inf")
    for zone in zones:
        value = zone.get("fvg_class")
        bonus = HTF_FVG_CLASS_BONUS.get(value, float("-inf"))
        if bonus > best_bonus:
            best = value
            best_bonus = bonus
    return best


def _recompute_merged_quality(zones, point, avg_range, timeframe_name):
    merged_high = max(float(max(zone["high"], zone["low"])) for zone in zones)
    merged_low = min(float(min(zone["low"], zone["high"])) for zone in zones)
    merged_width = max(merged_high - merged_low, 0.0)
    width_component = clamp(
        merged_width / max(float(avg_range) * HTF_FVG_QUALITY_DIVISOR, float(point) * HTF_FVG_MIN_POINTS, 1e-9)
    ) * HTF_FVG_QUALITY_SCALE
    components = {
        "base": HTF_FVG_QUALITY_BASE,
        "timeframe": HTF_FVG_TIMEFRAME_BONUS[timeframe_name],
        "width": width_component,
        "displacement": _max_component(zones, "displacement"),
        "bos": _max_component(zones, "bos"),
        "liquidity_sweep": _max_component(zones, "liquidity_sweep"),
        "trend_alignment": _max_component(zones, "trend_alignment"),
        "location": _max_component(zones, "location"),
        "follow_through": _max_component(zones, "follow_through"),
        "class_bonus": _max_component(zones, "class_bonus"),
    }
    penalties = {}
    for key in ("missing_context", "mid_range", "mitigation"):
        value = _max_penalty(zones, key)
        if value:
            penalties[key] = value
    quality = clamp(
        sum(float(value) for value in components.values()) - sum(float(value) for value in penalties.values())
    )
    return {
        "quality": quality,
        "components": {key: round(float(value), 4) for key, value in components.items()},
        "penalties": {key: round(float(value), 4) for key, value in penalties.items()},
    }


def _merge_fvg_cluster(zones, point, avg_range, timeframe_name):
    if len(zones) == 1:
        zone = dict(zones[0])
        zone["merged_source_indices"] = _flatten_merged_source_indices(zone)
        zone["component_count"] = _component_count(zone)
        return zone

    anchor = dict(_select_anchor_zone(zones))
    source_indices = sorted({index for zone in zones for index in _flatten_merged_source_indices(zone)})
    component_count = sum(_component_count(zone) for zone in zones)
    merged_quality = _recompute_merged_quality(zones, point, avg_range, timeframe_name)
    mitigation_rank = {"untouched": 0, "partially_mitigated": 1, "deep_mitigated": 2, "filled": 3, "invalidated": 4}
    mitigation_status = max(
        (zone.get("mitigation_status") for zone in zones),
        key=lambda value: mitigation_rank.get(value, -1),
    )
    anchor.update(
        {
            "low": min(float(zone["low"]) for zone in zones),
            "high": max(float(zone["high"]) for zone in zones),
            "source_index": min(source_indices) if source_indices else None,
            "quality": merged_quality["quality"],
            "quality_components": merged_quality["components"],
            "quality_penalties": merged_quality["penalties"],
            "formed_in_displacement": any(bool(zone.get("formed_in_displacement")) for zone in zones),
            "tradable": any(bool(zone.get("tradable")) for zone in zones)
            and merged_quality["quality"] >= HTF_FVG_TRADABLE_MIN_QUALITY,
            "valid_fvg": all(bool(zone.get("valid_fvg", True)) for zone in zones),
            "displacement_strength": _combine_strength(zones, "displacement_strength", {"weak": 0, "medium": 1, "strong": 2}),
            "after_bos": any(bool(zone.get("after_bos")) for zone in zones),
            "near_liquidity_sweep": any(bool(zone.get("near_liquidity_sweep")) for zone in zones),
            "trend_aligned": any(bool(zone.get("trend_aligned")) for zone in zones),
            "follow_through_strength": _combine_strength(zones, "follow_through_strength", {"weak": 0, "moderate": 1, "strong": 2}),
            "follow_through_confirmed": any(bool(zone.get("follow_through_confirmed")) for zone in zones),
            "mitigation_status": mitigation_status,
            "mitigation_ratio": max(float(zone.get("mitigation_ratio") or 0.0) for zone in zones),
            "fvg_class": _combine_class(zones),
            "merged_source_indices": source_indices,
            "component_count": component_count,
        }
    )
    return anchor


def _cluster_envelope(cluster, timeframe_name):
    envelope = dict(cluster[0])
    envelope.setdefault("timeframe", timeframe_name)
    envelope["low"] = min(float(zone["low"]) for zone in cluster)
    envelope["high"] = max(float(zone["high"]) for zone in cluster)
    source_indices = sorted({index for zone in cluster for index in _flatten_merged_source_indices(zone)})
    envelope["source_index"] = min(source_indices) if source_indices else None
    envelope["merged_source_indices"] = source_indices
    return envelope


def merge_fvg_zones(zones, point, avg_range, timeframe_name):
    if not zones:
        return []

    ordered = sorted(
        zones,
        key=lambda zone: (
            str(zone.get("timeframe") or timeframe_name).upper(),
            str(zone.get("bias") or ""),
            float(min(zone["low"], zone["high"])),
            float(max(zone["low"], zone["high"])),
            int(zone.get("source_index") or 0),
        ),
    )
    merged = []
    cluster = []

    for zone in ordered:
        candidate = dict(zone)
        candidate.setdefault("timeframe", timeframe_name)
        if not cluster:
            cluster = [candidate]
            continue

        if should_merge_fvg_zones(_cluster_envelope(cluster, timeframe_name), candidate, point, avg_range):
            cluster.append(candidate)
            continue

        merged.append(_merge_fvg_cluster(cluster, point, avg_range, timeframe_name))
        cluster = [candidate]

    if cluster:
        merged.append(_merge_fvg_cluster(cluster, point, avg_range, timeframe_name))

    return merged


def find_fvgs(rates, timeframe_name, avg_range, point, zone_builder):
    swings = build_swing_structure(rates, avg_range)
    zones = []
    for candidate in find_fvg_candidates(rates):
        validation = assess_fvg_candidate(candidate, rates, timeframe_name, avg_range, point, swings=swings)
        if not validation["keep"]:
            continue

        zones.append(
            zone_builder(
                label=f"{timeframe_name} FVG",
                timeframe=timeframe_name,
                zone_type="FVG",
                bias=candidate["bias"],
                low=candidate["low"],
                high=candidate["high"],
                quality=validation["quality"],
                source_index=candidate["source_index"],
                formed_in_displacement=validation["formed_in_displacement"],
                geometric_fvg=True,
                valid_fvg=validation["valid"],
                tradable=validation["tradable"],
                displacement_strength=validation["displacement_strength"],
                after_bos=validation["after_bos"],
                near_liquidity_sweep=validation["near_liquidity_sweep"],
                trend=validation["trend"],
                trend_aligned=validation["trend_aligned"],
                location_in_range=validation["location_in_range"],
                fvg_class=validation["fvg_class"],
                mitigation_status=validation["mitigation_status"],
                mitigation_ratio=validation["mitigation_ratio"],
                follow_through_strength=validation["follow_through_strength"],
                follow_through_confirmed=validation["follow_through_confirmed"],
                follow_through_fill_ratio=validation["follow_through_fill_ratio"],
                quality_components=validation["quality_components"],
                quality_penalties=validation["quality_penalties"],
                context_signals=validation["context_signals"],
                rejection_reason=validation["rejection_reason"],
                bos_index=validation["bos_index"],
                sweep_index=validation["sweep_index"],
                fvg_debug=validation["debug"],
            )
        )

    zones = merge_fvg_zones(zones, point, avg_range, timeframe_name)
    zones.sort(
        key=lambda zone: (
            zone["quality"],
            1 if zone.get("tradable") else 0,
            zone["source_index"],
        ),
        reverse=True,
    )
    return zones[:HTF_FVG_MAX_ZONES]
