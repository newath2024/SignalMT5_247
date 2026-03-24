from ..config.htf import (
    HTF_PREVIOUS_DAY_QUALITY,
    HTF_SESSION_ASIA_QUALITY,
    HTF_SESSION_BAND_MULTIPLIER,
    HTF_SESSION_LONDON_QUALITY,
    HTF_PREVIOUS_WEEK_BAND_MULTIPLIER,
    HTF_PREVIOUS_WEEK_QUALITY,
    HTF_REFERENCE_BAND_H1_RATIO,
    HTF_REFERENCE_BAND_H4_RATIO,
    HTF_REFERENCE_BAND_MIN_POINTS,
)
from ..patterns.fvg import find_fvgs as detect_fvgs
from ..patterns.ob import find_order_blocks as detect_order_blocks
from .filters import is_fvg_valid, is_ob_valid
from ..utils import average_range, clamp, zone_distance, zone_mid, zone_width


CORE_REFERENCE_KEYS = {"PDH", "PDL", "PWH", "PWL"}
SESSION_REFERENCE_KEYS = {"ASH", "ASL", "LOH", "LOL"}


def _classify_zone_tier(zone_type, timeframe, *, reference_key=None, tradable=False):
    zone_type = str(zone_type or "").upper()
    timeframe = str(timeframe or "").upper()
    reference_key = str(reference_key or "").upper()

    if reference_key in CORE_REFERENCE_KEYS:
        return "A"
    if zone_type == "OB" and timeframe == "H4":
        return "A"
    if zone_type == "FVG" and timeframe == "H4" and bool(tradable):
        return "A"
    if zone_type in {"OB", "FVG"} and timeframe in {"H1", "M30"}:
        return "B"
    if reference_key in SESSION_REFERENCE_KEYS:
        return "C"
    if zone_type == "FVG" and timeframe == "H4":
        return "B"
    return "B"


def _zone_metadata(label, timeframe, zone_type, *, reference_key=None, tradable=False):
    reference_key = str(reference_key or "").upper()
    tier = _classify_zone_tier(zone_type, timeframe, reference_key=reference_key, tradable=tradable)
    is_session_level = reference_key in SESSION_REFERENCE_KEYS
    is_liquidity_level = bool(reference_key) or "HIGH" in str(zone_type or "").upper() or "LOW" in str(zone_type or "").upper()
    is_structural = str(zone_type or "").upper() in {"OB", "FVG"}
    base_confluence = is_structural and tier in {"A", "B"}
    return {
        "tier": tier,
        "is_structural": is_structural,
        "is_session_level": is_session_level,
        "is_liquidity_level": is_liquidity_level,
        "has_confluence": base_confluence,
        "has_structural_zone_nearby": False,
        "has_higher_timeframe_backing": tier == "A",
        "context_strength": "moderate" if tier in {"A", "B"} else "weak",
    }


def _zone_proximity_threshold(zone, point):
    tolerance = float(zone.get("tolerance") or 0.0)
    width = zone_width(zone)
    return max(tolerance, width * 0.75, float(point) * 12.0)


def annotate_zone_relationships(zones, point):
    if not zones:
        return zones

    for zone in zones:
        zone.setdefault("has_confluence", False)
        zone.setdefault("has_structural_zone_nearby", False)
        zone.setdefault("has_higher_timeframe_backing", zone.get("tier") == "A")
        zone.setdefault("context_strength", "moderate" if zone.get("tier") in {"A", "B"} else "weak")

    for index, zone in enumerate(zones):
        threshold = _zone_proximity_threshold(zone, point)
        midpoint = zone_mid(zone)
        for other_index, other in enumerate(zones):
            if index == other_index:
                continue

            other_midpoint = zone_mid(other)
            proximity = max(threshold, _zone_proximity_threshold(other, point))
            if abs(midpoint - other_midpoint) > proximity and zone_distance(midpoint, other["low"], other["high"]) > proximity:
                continue

            if other.get("is_structural"):
                zone["has_structural_zone_nearby"] = True
            if other.get("tier") == "A" or str(other.get("timeframe") or "").upper() in {"W1", "D1", "H4"}:
                zone["has_higher_timeframe_backing"] = True

        if zone.get("has_structural_zone_nearby") or zone.get("has_higher_timeframe_backing"):
            zone["has_confluence"] = True
            if zone.get("tier") == "C":
                zone["context_strength"] = "moderate"

    return zones


def make_zone(label, timeframe, zone_type, bias, low, high, quality, source_index=None, **extra):
    low_value = float(min(low, high))
    high_value = float(max(low, high))
    metadata = _zone_metadata(
        label,
        timeframe,
        zone_type,
        reference_key=extra.get("reference_key"),
        tradable=bool(extra.get("tradable")),
    )
    zone = {
        "label": label,
        "timeframe": timeframe,
        "type": zone_type,
        "bias": bias,
        "low": low_value,
        "high": high_value,
        "quality": clamp(float(quality)),
        "source_index": source_index,
    }
    zone.update(metadata)
    zone.update(extra)
    return zone


def find_order_blocks(rates, timeframe_name, avg_range, point):
    zones = detect_order_blocks(rates, timeframe_name, avg_range, point, zone_builder=make_zone)
    # Drop invalidated OB zones before they reach HTF context or downstream LTF flow.
    return [zone for zone in zones if is_ob_valid(zone, rates, len(rates) - 1)]


def find_fvgs(rates, timeframe_name, avg_range, point=0.0):
    zones = detect_fvgs(rates, timeframe_name, avg_range, point, zone_builder=make_zone)
    # Drop invalidated FVG zones before they reach HTF context or downstream LTF flow.
    return [zone for zone in zones if is_fvg_valid(zone, rates, len(rates) - 1)]


def build_previous_levels(rates_d1, rates_w1, band):
    zones = []
    if rates_d1 is not None and len(rates_d1) >= 1:
        prev_day = rates_d1[-1]
        zones.append(
            make_zone(
                label="Previous Day High",
                timeframe="D1",
                zone_type="Previous Day High",
                bias="Neutral",
                low=prev_day["high"],
                high=prev_day["high"],
                quality=HTF_PREVIOUS_DAY_QUALITY,
                is_liquidity_level=True,
                liquidity_level=float(prev_day["high"]),
                tolerance=float(band),
                source_time=int(prev_day["time"]),
                reference_key="PDH",
            )
        )
        zones.append(
            make_zone(
                label="Previous Day Low",
                timeframe="D1",
                zone_type="Previous Day Low",
                bias="Neutral",
                low=prev_day["low"],
                high=prev_day["low"],
                quality=HTF_PREVIOUS_DAY_QUALITY,
                is_liquidity_level=True,
                liquidity_level=float(prev_day["low"]),
                tolerance=float(band),
                source_time=int(prev_day["time"]),
                reference_key="PDL",
            )
        )

    if rates_w1 is not None and len(rates_w1) >= 1:
        weekly_band = band * HTF_PREVIOUS_WEEK_BAND_MULTIPLIER
        prev_week = rates_w1[-1]
        zones.append(
            make_zone(
                label="Previous Week High",
                timeframe="W1",
                zone_type="Previous Week High",
                bias="Neutral",
                low=prev_week["high"],
                high=prev_week["high"],
                quality=HTF_PREVIOUS_WEEK_QUALITY,
                is_liquidity_level=True,
                liquidity_level=float(prev_week["high"]),
                tolerance=float(weekly_band),
                source_time=int(prev_week["time"]),
                reference_key="PWH",
            )
        )
        zones.append(
            make_zone(
                label="Previous Week Low",
                timeframe="W1",
                zone_type="Previous Week Low",
                bias="Neutral",
                low=prev_week["low"],
                high=prev_week["low"],
                quality=HTF_PREVIOUS_WEEK_QUALITY,
                is_liquidity_level=True,
                liquidity_level=float(prev_week["low"]),
                tolerance=float(weekly_band),
                source_time=int(prev_week["time"]),
                reference_key="PWL",
            )
        )

    return zones


def build_session_levels(reference_levels, band):
    zones = []
    if not reference_levels:
        return zones

    session_band = float(band) * HTF_SESSION_BAND_MULTIPLIER
    session_specs = (
        ("ASH", "Asia Session High", HTF_SESSION_ASIA_QUALITY),
        ("ASL", "Asia Session Low", HTF_SESSION_ASIA_QUALITY),
        ("LOH", "London Session High", HTF_SESSION_LONDON_QUALITY),
        ("LOL", "London Session Low", HTF_SESSION_LONDON_QUALITY),
    )
    for reference_key, label, quality in session_specs:
        level = reference_levels.get(reference_key)
        if level is None:
            continue
        zones.append(
            make_zone(
                label=label,
                timeframe="SESSION",
                zone_type=label,
                bias="Neutral",
                low=level,
                high=level,
                quality=quality,
                is_liquidity_level=True,
                liquidity_level=float(level),
                tolerance=session_band,
                reference_key=reference_key,
            )
        )

    return zones


def build_htf_zones(snapshot):
    rates = snapshot["rates"]
    point = snapshot["point"]
    avg_m30 = average_range(rates["M30"], 20)
    avg_h1 = average_range(rates["H1"], 20)
    avg_h4 = average_range(rates["H4"], 20)
    reference_band = max(
        avg_h1 * HTF_REFERENCE_BAND_H1_RATIO,
        avg_h4 * HTF_REFERENCE_BAND_H4_RATIO,
        point * HTF_REFERENCE_BAND_MIN_POINTS,
    )

    zones = []
    zones.extend(find_order_blocks(rates["M30"], "M30", avg_m30, point))
    zones.extend(find_order_blocks(rates["H1"], "H1", avg_h1, point))
    zones.extend(find_order_blocks(rates["H4"], "H4", avg_h4, point))
    zones.extend(find_fvgs(rates["M30"], "M30", avg_m30, point))
    zones.extend(find_fvgs(rates["H1"], "H1", avg_h1, point))
    zones.extend(find_fvgs(rates["H4"], "H4", avg_h4, point))
    zones.extend(build_session_levels(snapshot.get("reference_levels") or {}, reference_band))
    zones.extend(build_previous_levels(rates["D1"], rates["W1"], reference_band))
    return annotate_zone_relationships(zones, point)
