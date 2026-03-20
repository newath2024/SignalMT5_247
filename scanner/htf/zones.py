from ..config.htf import (
    HTF_PREVIOUS_DAY_QUALITY,
    HTF_PREVIOUS_WEEK_BAND_MULTIPLIER,
    HTF_PREVIOUS_WEEK_QUALITY,
    HTF_REFERENCE_BAND_H1_RATIO,
    HTF_REFERENCE_BAND_H4_RATIO,
    HTF_REFERENCE_BAND_MIN_POINTS,
)
from ..patterns.fvg import find_fvgs as detect_fvgs
from ..patterns.ob import find_order_blocks as detect_order_blocks
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
    return detect_order_blocks(rates, timeframe_name, avg_range, point, zone_builder=make_zone)


def find_fvgs(rates, timeframe_name, avg_range, point=0.0):
    return detect_fvgs(rates, timeframe_name, avg_range, point, zone_builder=make_zone)


def build_previous_levels(rates_d1, rates_w1, band):
    zones = []
    if rates_d1 is not None and len(rates_d1) >= 1:
        prev_day = rates_d1[-1]
        zones.append(
            make_zone(
                label="Previous Day High",
                timeframe="D1",
                zone_type="Previous Day High",
                bias="Short",
                low=prev_day["high"] - band,
                high=prev_day["high"] + band,
                quality=HTF_PREVIOUS_DAY_QUALITY,
            )
        )
        zones.append(
            make_zone(
                label="Previous Day Low",
                timeframe="D1",
                zone_type="Previous Day Low",
                bias="Long",
                low=prev_day["low"] - band,
                high=prev_day["low"] + band,
                quality=HTF_PREVIOUS_DAY_QUALITY,
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
                bias="Short",
                low=prev_week["high"] - weekly_band,
                high=prev_week["high"] + weekly_band,
                quality=HTF_PREVIOUS_WEEK_QUALITY,
            )
        )
        zones.append(
            make_zone(
                label="Previous Week Low",
                timeframe="W1",
                zone_type="Previous Week Low",
                bias="Long",
                low=prev_week["low"] - weekly_band,
                high=prev_week["low"] + weekly_band,
                quality=HTF_PREVIOUS_WEEK_QUALITY,
            )
        )

    return zones


def build_htf_zones(snapshot):
    rates = snapshot["rates"]
    point = snapshot["point"]
    avg_h1 = average_range(rates["H1"], 20)
    avg_h4 = average_range(rates["H4"], 20)
    reference_band = max(
        avg_h1 * HTF_REFERENCE_BAND_H1_RATIO,
        avg_h4 * HTF_REFERENCE_BAND_H4_RATIO,
        point * HTF_REFERENCE_BAND_MIN_POINTS,
    )

    zones = []
    zones.extend(find_order_blocks(rates["H1"], "H1", avg_h1, point))
    zones.extend(find_order_blocks(rates["H4"], "H4", avg_h4, point))
    zones.extend(find_fvgs(rates["H1"], "H1", avg_h1, point))
    zones.extend(find_fvgs(rates["H4"], "H4", avg_h4, point))
    zones.extend(build_previous_levels(rates["D1"], rates["W1"], reference_band))
    return zones
