"""Structural HTF zone builder used by the active strategy runtime.

This module intentionally excludes previous day/week and session high/low
levels. Active HTF context is derived only from structural OB/FVG zones.
"""

from __future__ import annotations

from ..patterns.fvg import find_fvgs as detect_fvgs
from ..patterns.ob import find_order_blocks as detect_order_blocks
from ..utils import average_range, clamp, zone_distance, zone_mid, zone_width
from .filters import is_fvg_valid, is_ob_valid


STRUCTURAL_TIMEFRAMES: tuple[str, ...] = ("M15", "M30", "H1", "H4")


def _classify_zone_tier(zone_type, timeframe, *, tradable=False):
    zone_type = str(zone_type or "").upper()
    timeframe = str(timeframe or "").upper()

    if zone_type == "OB" and timeframe == "H4":
        return "A"
    if zone_type == "FVG" and timeframe == "H4" and bool(tradable):
        return "A"
    if zone_type in {"OB", "FVG"} and timeframe in {"H1", "M30"}:
        return "B"
    if zone_type in {"OB", "FVG"} and timeframe == "M15":
        return "C"
    if zone_type == "FVG" and timeframe == "H4":
        return "B"
    return "C"


def _zone_metadata(label, timeframe, zone_type, *, tradable=False):
    tier = _classify_zone_tier(zone_type, timeframe, tradable=tradable)
    return {
        "tier": tier,
        "is_structural": True,
        "is_session_level": False,
        "is_liquidity_level": False,
        "has_confluence": tier in {"A", "B"},
        "has_structural_zone_nearby": False,
        "has_higher_timeframe_backing": tier == "A",
        "context_strength": "strong" if tier == "A" else "moderate" if tier == "B" else "weak",
    }


def _zone_proximity_threshold(zone, point):
    tolerance = float(zone.get("tolerance") or 0.0)
    width = zone_width(zone)
    return max(tolerance, width * 0.75, float(point) * 12.0)


def annotate_zone_relationships(zones, point):
    if not zones:
        return zones

    for zone in zones:
        zone.setdefault("has_confluence", zone.get("tier") in {"A", "B"})
        zone.setdefault("has_structural_zone_nearby", False)
        zone.setdefault("has_higher_timeframe_backing", zone.get("tier") == "A")
        zone.setdefault(
            "context_strength",
            "strong" if zone.get("tier") == "A" else "moderate" if zone.get("tier") == "B" else "weak",
        )

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
            if str(other.get("timeframe") or "").upper() in {"H4"} or other.get("tier") == "A":
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
    return [zone for zone in zones if is_ob_valid(zone, rates, len(rates) - 1)]


def find_fvgs(rates, timeframe_name, avg_range, point=0.0):
    zones = detect_fvgs(rates, timeframe_name, avg_range, point, zone_builder=make_zone)
    return [zone for zone in zones if is_fvg_valid(zone, rates, len(rates) - 1)]


def build_htf_zones(snapshot):
    rates = snapshot["rates"]
    point = snapshot["point"]
    zones = []

    for timeframe_name in STRUCTURAL_TIMEFRAMES:
        timeframe_rates = rates.get(timeframe_name)
        if timeframe_rates is None or len(timeframe_rates) == 0:
            continue
        avg_range = average_range(timeframe_rates, 20)
        zones.extend(find_order_blocks(timeframe_rates, timeframe_name, avg_range, point))
        zones.extend(find_fvgs(timeframe_rates, timeframe_name, avg_range, point))

    return annotate_zone_relationships(zones, point)
