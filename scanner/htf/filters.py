from ..config.htf import (
    HTF_CLEAR_DISTANCE_THRESHOLD,
    HTF_CLEAR_REACTION_THRESHOLD,
    HTF_CLEAR_ZONE_QUALITY_THRESHOLD,
    HTF_COMPOSITE_DISTANCE_WEIGHT,
    HTF_DISTANCE_BODY_THRESHOLD,
    HTF_DISTANCE_NEAR_THRESHOLD,
    HTF_EVALUATION_RECENT_BARS,
    HTF_OB_INVALIDATION_BUFFER,
    HTF_OB_INVALIDATION_USE_CLOSE,
    HTF_REACTION_NEAR,
    HTF_REACTION_NEAR_WITH_BODY,
    HTF_REACTION_RESPECTED,
    HTF_REACTION_STRONG,
    HTF_SWEEP_BUFFER_POINTS,
    HTF_TOLERANCE_AVG_H1_RATIO,
    HTF_TOLERANCE_MIN_POINTS,
    HTF_TOLERANCE_ZONE_WIDTH_RATIO,
)
from ..structure.swings import summarize_market_structure
from ..utils import average_range, clamp, zone_distance, zone_mid, zone_width


def determine_htf_structure(snapshot):
    rates_h1 = snapshot["rates"]["H1"]
    rates_h4 = snapshot["rates"]["H4"]
    avg_h1 = average_range(rates_h1, 20)
    avg_h4 = average_range(rates_h4, 20)
    h1_structure = summarize_market_structure(rates_h1, avg_h1)
    h4_structure = summarize_market_structure(rates_h4, avg_h4)

    if h4_structure["clear"]:
        trend = h4_structure["trend"]
        clear = trend != "Range"
    elif h1_structure["clear"]:
        trend = h1_structure["trend"]
        clear = trend != "Range"
    else:
        trend = "Range"
        clear = False

    return {
        "trend": trend,
        "clear": clear,
        "H1": h1_structure,
        "H4": h4_structure,
    }


def is_ob_valid(ob_zone, rates, current_index) -> bool:
    if ob_zone is None or rates is None or len(rates) == 0:
        return False

    source_index = ob_zone.get("source_index")
    if source_index is None:
        return True

    last_index = min(int(current_index), len(rates) - 1)
    start_index = int(source_index) + 1
    if start_index > last_index:
        return True

    low = float(ob_zone["low"])
    high = float(ob_zone["high"])
    bias = ob_zone.get("bias")
    buffer = float(HTF_OB_INVALIDATION_BUFFER or 0.0)

    for index in range(start_index, last_index + 1):
        candle = rates[index]
        if HTF_OB_INVALIDATION_USE_CLOSE:
            value = float(candle["close"])
            if bias == "Long" and value < low - buffer:
                return False
            if bias == "Short" and value > high + buffer:
                return False
            continue

        if bias == "Long" and float(candle["low"]) < low - buffer:
            return False
        if bias == "Short" and float(candle["high"]) > high + buffer:
            return False

    return True


def evaluate_htf_zone(zone, snapshot, structure=None):
    price = snapshot["current_price"]
    point = snapshot["point"]
    rates_h1 = snapshot["rates"]["H1"]
    rates_h4 = snapshot["rates"]["H4"]
    avg_h1 = average_range(rates_h1, 20)
    structure = structure or determine_htf_structure(snapshot)
    zone_rates = rates_h4 if zone["timeframe"] == "H4" else rates_h1
    zone_valid = True
    invalidation_reason = None
    if zone.get("type") == "OB":
        zone_valid = is_ob_valid(zone, zone_rates, len(zone_rates) - 1)
        if not zone_valid:
            invalidation_reason = "OB invalidated by close break"

    if not zone_valid:
        return {
            "zone": zone,
            "bias": zone["bias"],
            "zone_quality": zone["quality"],
            "reaction_clarity": 0.0,
            "distance_score": 0.0,
            "structure_trend": structure["trend"],
            "trend_alignment": "invalidated",
            "clear": False,
            "score": -1.0,
            "valid": False,
            "invalidation_reason": invalidation_reason,
        }

    recent_bars = (
        rates_h4[-HTF_EVALUATION_RECENT_BARS["H4"] :]
        if zone["timeframe"] == "H4"
        else rates_h1[-HTF_EVALUATION_RECENT_BARS["H1"] :]
    )
    tolerance = max(
        zone_width(zone) * HTF_TOLERANCE_ZONE_WIDTH_RATIO,
        avg_h1 * HTF_TOLERANCE_AVG_H1_RATIO,
        point * HTF_TOLERANCE_MIN_POINTS,
    )
    distance = zone_distance(price, zone["low"], zone["high"])
    distance_score = clamp(1.0 - distance / max(tolerance, point))

    last_close = float(recent_bars[-1]["close"])
    last_open = float(recent_bars[-1]["open"])
    highest_recent = float(recent_bars["high"].max())
    lowest_recent = float(recent_bars["low"].min())
    midpoint = zone_mid(zone)

    if zone["bias"] == "Long":
        sweep = lowest_recent < zone["low"] - point * HTF_SWEEP_BUFFER_POINTS and last_close >= zone["low"]
        respected = (
            lowest_recent <= zone["high"] + tolerance
            and last_close > last_open
            and last_close >= midpoint
        )
        if sweep and last_close >= midpoint:
            reaction = HTF_REACTION_STRONG
        elif respected:
            reaction = HTF_REACTION_RESPECTED
        elif distance_score >= HTF_DISTANCE_BODY_THRESHOLD and last_close > last_open:
            reaction = HTF_REACTION_NEAR_WITH_BODY
        elif distance_score >= HTF_DISTANCE_NEAR_THRESHOLD:
            reaction = HTF_REACTION_NEAR
        else:
            reaction = 0.0
    else:
        sweep = highest_recent > zone["high"] + point * HTF_SWEEP_BUFFER_POINTS and last_close <= zone["high"]
        respected = (
            highest_recent >= zone["low"] - tolerance
            and last_close < last_open
            and last_close <= midpoint
        )
        if sweep and last_close <= midpoint:
            reaction = HTF_REACTION_STRONG
        elif respected:
            reaction = HTF_REACTION_RESPECTED
        elif distance_score >= HTF_DISTANCE_BODY_THRESHOLD and last_close < last_open:
            reaction = HTF_REACTION_NEAR_WITH_BODY
        elif distance_score >= HTF_DISTANCE_NEAR_THRESHOLD:
            reaction = HTF_REACTION_NEAR
        else:
            reaction = 0.0

    clear = reaction >= HTF_CLEAR_REACTION_THRESHOLD or (
        distance_score >= HTF_CLEAR_DISTANCE_THRESHOLD
        and zone["quality"] >= HTF_CLEAR_ZONE_QUALITY_THRESHOLD
    )
    trend = structure["trend"]
    trend_alignment = "range"
    if trend == "Bullish":
        trend_alignment = "aligned" if zone["bias"] == "Long" else "countertrend"
    elif trend == "Bearish":
        trend_alignment = "aligned" if zone["bias"] == "Short" else "countertrend"

    if structure["clear"] and trend_alignment == "countertrend":
        clear = False

    composite = zone["quality"] + reaction + distance_score * HTF_COMPOSITE_DISTANCE_WEIGHT
    if trend_alignment == "aligned":
        composite += 0.05
    elif trend_alignment == "countertrend":
        composite -= 0.2

    return {
        "zone": zone,
        "bias": zone["bias"],
        "zone_quality": zone["quality"],
        "reaction_clarity": reaction,
        "distance_score": distance_score,
        "structure_trend": trend,
        "trend_alignment": trend_alignment,
        "clear": clear,
        "score": composite,
        "valid": True,
        "invalidation_reason": None,
    }
