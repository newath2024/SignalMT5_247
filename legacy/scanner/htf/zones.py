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
from ..utils import average_range, clamp


def make_zone(label, timeframe, zone_type, bias, low, high, quality, source_index=None, **extra):
    low_value = float(min(low, high))
    high_value = float(max(low, high))
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
    return zones
