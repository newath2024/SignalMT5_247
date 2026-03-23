from ..config.htf import (
    HTF_OB_REQUIRE_LIQUIDITY_SWEEP,
    HTF_BOS_CLOSE_BUFFER_POINTS,
    HTF_BOS_WICK_BUFFER_POINTS,
    HTF_DISPLACEMENT_MAX_OPPOSITE_BARS,
    HTF_DISPLACEMENT_MAX_WEAK_BODY_BARS,
    HTF_DISPLACEMENT_MIN_BARS,
    HTF_DISPLACEMENT_MIN_BODY_MEDIUM,
    HTF_DISPLACEMENT_MIN_BODY_STRONG,
    HTF_DISPLACEMENT_MIN_DIRECTIONAL_RATIO,
    HTF_DISPLACEMENT_MIN_EFFICIENCY_MEDIUM,
    HTF_DISPLACEMENT_MIN_EFFICIENCY_STRONG,
    HTF_DISPLACEMENT_MIN_MOVE_MEDIUM,
    HTF_DISPLACEMENT_MIN_MOVE_STRONG,
    HTF_FVG_DISPLACEMENT_BODY_THRESHOLD,
    HTF_FVG_MIN_GAP_RATIO,
    HTF_FVG_MIN_POINTS,
    HTF_ORDER_BLOCK_MAX_LOOKAHEAD,
    HTF_ORDER_BLOCK_MAX_OVERLAP_BARS,
    HTF_ORDER_BLOCK_OVERLAP_TOLERANCE_POINTS,
    HTF_SWEEP_BUFFER_POINTS,
)
from ..config.ltf import (
    LTF_IFVG_ENTRY_DISTANCE_MIN_POINTS,
    LTF_IFVG_ENTRY_DISTANCE_RANGE_RATIO,
    LTF_IFVG_ENTRY_DISTANCE_WIDTH_RATIO,
    LTF_IFVG_ENTRY_MIN_QUALITY,
    LTF_IFVG_INTERNAL_MIN_ENTRY_QUALITY,
    LTF_IFVG_MIN_POINTS,
    LTF_IFVG_MIN_WIDTH_RATIO,
    LTF_IFVG_POST_BREAK_BARS,
)
from ..utils import body_strength, clamp, zone_distance
from .displacement import displacement_strength
from .fvg_assessment import assess_fvg_candidate
from .swings import (
    build_swing_structure,
    get_last_confirmed_swing_high_before,
    get_last_confirmed_swing_low_before,
)


def has_overlap_after_zone(rates, zone_low, zone_high, start_index, end_index, point):
    overlap_bars = []
    tolerance = point * HTF_ORDER_BLOCK_OVERLAP_TOLERANCE_POINTS

    for index in range(start_index, min(len(rates), end_index + 1)):
        candle_low = float(rates["low"][index])
        candle_high = float(rates["high"][index])
        overlaps = candle_high >= zone_low - tolerance and candle_low <= zone_high + tolerance
        if overlaps:
            overlap_bars.append(index)

    return {
        "count": len(overlap_bars),
        "indices": overlap_bars,
        "valid": len(overlap_bars) <= HTF_ORDER_BLOCK_MAX_OVERLAP_BARS,
    }


def has_clean_post_ob_move(rates, candidate, break_index, point):
    overlap_start = int(candidate.get("engulf_index", candidate["source_index"])) + 1
    overlap = has_overlap_after_zone(
        rates,
        candidate["low"],
        candidate["high"],
        overlap_start,
        break_index,
        point,
    )
    return overlap["valid"], overlap


def has_liquidity_sweep(rates, candidate, swings, point):
    if candidate["bias"] == "Long":
        reference_swing = get_last_confirmed_swing_low_before(swings["lows"], candidate["source_index"])
        if reference_swing is None:
            return False
        return float(rates["low"][candidate["source_index"]]) < reference_swing["price"] - point * HTF_SWEEP_BUFFER_POINTS

    reference_swing = get_last_confirmed_swing_high_before(swings["highs"], candidate["source_index"])
    if reference_swing is None:
        return False
    return float(rates["high"][candidate["source_index"]]) > reference_swing["price"] + point * HTF_SWEEP_BUFFER_POINTS


def is_valid_bos(rates, index, bias, avg_range, point, swing_window=2, swings=None):
    if swings is None:
        swings = build_swing_structure(rates, avg_range, left=swing_window, right=swing_window)

    if bias == "Long":
        reference_swing = get_last_confirmed_swing_high_before(swings["highs"], index)
    else:
        reference_swing = get_last_confirmed_swing_low_before(swings["lows"], index)

    if reference_swing is None:
        return {"valid": False, "bos_valid": False, "break_index": None, "swing": None, "displacement": None}

    closes = rates["close"]
    highs = rates["high"]
    lows = rates["low"]
    for break_index in range(index + 1, min(len(rates), index + 1 + HTF_ORDER_BLOCK_MAX_LOOKAHEAD)):
        if bias == "Long":
            close_break = float(closes[break_index]) > reference_swing["price"] + point * HTF_BOS_CLOSE_BUFFER_POINTS
            wick_break = float(highs[break_index]) > reference_swing["price"] + point * HTF_BOS_WICK_BUFFER_POINTS
        else:
            close_break = float(closes[break_index]) < reference_swing["price"] - point * HTF_BOS_CLOSE_BUFFER_POINTS
            wick_break = float(lows[break_index]) < reference_swing["price"] - point * HTF_BOS_WICK_BUFFER_POINTS

        if not (close_break and wick_break):
            continue

        displacement = displacement_strength(rates, index + 1, break_index, bias, avg_range, point)
        if displacement is None:
            continue

        return {
            "valid": displacement["valid"],
            "bos_valid": displacement["valid"],
            "break_index": break_index,
            "swing": reference_swing,
            "displacement": displacement,
        }

    return {"valid": False, "bos_valid": False, "break_index": None, "swing": reference_swing, "displacement": None}


def is_valid_ob(rates, candidate, avg_range, point, swings, trend, has_fvg=False):
    bos = is_valid_bos(rates, candidate["source_index"], candidate["bias"], avg_range, point, swings=swings)
    if not bos["valid"]:
        return {"valid": False, "bos_valid": False, "break_index": bos["break_index"], "swing": bos["swing"]}

    clean_move, overlap = has_clean_post_ob_move(rates, candidate, bos["break_index"], point)
    if not clean_move:
        return {
            "valid": False,
            "bos_valid": True,
            "break_index": bos["break_index"],
            "swing": bos["swing"],
            "displacement": bos["displacement"],
            "overlap": overlap,
        }

    trend_aligned = (
        (candidate["bias"] == "Long" and trend == "Bullish")
        or (candidate["bias"] == "Short" and trend == "Bearish")
    )
    liquidity_sweep = has_liquidity_sweep(rates, candidate, swings, point)
    if HTF_OB_REQUIRE_LIQUIDITY_SWEEP and not liquidity_sweep:
        return {
            "valid": False,
            "bos_valid": True,
            "break_index": bos["break_index"],
            "swing": bos["swing"],
            "displacement": bos["displacement"],
            "overlap": overlap,
            "liquidity_sweep": liquidity_sweep,
            "trend": trend,
            "trend_aligned": trend_aligned,
        }

    countertrend = (
        (candidate["bias"] == "Long" and trend == "Bearish")
        or (candidate["bias"] == "Short" and trend == "Bullish")
    )
    if countertrend and not liquidity_sweep:
        return {
            "valid": False,
            "bos_valid": True,
            "break_index": bos["break_index"],
            "swing": bos["swing"],
            "displacement": bos["displacement"],
            "overlap": overlap,
            "liquidity_sweep": liquidity_sweep,
            "trend": trend,
            "trend_aligned": trend_aligned,
        }

    priority_rank = "OB + FVG" if has_fvg else ("OB + liquidity sweep" if liquidity_sweep else "OB only")
    return {
        "valid": True,
        "bos_valid": True,
        "break_index": bos["break_index"],
        "swing": bos["swing"],
        "displacement": bos["displacement"],
        "overlap": overlap,
        "has_fvg": has_fvg,
        "liquidity_sweep": liquidity_sweep,
        "trend": trend,
        "trend_aligned": trend_aligned,
        "priority_rank": priority_rank,
    }


def is_valid_fvg(candidate, rates, avg_range, point):
    timeframe_name = str(candidate.get("timeframe") or "H1")
    return assess_fvg_candidate(candidate, rates, timeframe_name, avg_range, point)


def find_first_touch_after_creation(rates, source_index, zone_low, zone_high):
    highs = rates["high"]
    lows = rates["low"]
    for index in range(source_index + 1, len(rates)):
        if float(highs[index]) >= zone_low and float(lows[index]) <= zone_high:
            return index
    return None


def is_clean_ifvg_inversion(rates, bias, source_index, zone_low, zone_high, point):
    touch_index = find_first_touch_after_creation(rates, source_index, zone_low, zone_high)
    if touch_index is None:
        return False, None

    if bias == "Long":
        clean_inversion = float(rates["high"][touch_index]) > zone_high + point
    else:
        clean_inversion = float(rates["low"][touch_index]) < zone_low - point

    return clean_inversion, touch_index


def _has_meaningful_post_break_confirmation(rates, bias, confirmation_index, zone_low, zone_high):
    if confirmation_index is None:
        return False

    closes = rates["close"][confirmation_index : min(len(rates), confirmation_index + LTF_IFVG_POST_BREAK_BARS)]
    if len(closes) == 0:
        return False
    if bias == "Long":
        return float(closes.max()) > zone_high
    return float(closes.min()) < zone_low


def is_valid_ifvg(candidate, rates, bias, confirmation_index, current_price, avg_range, point):
    zone_low = float(candidate["low"])
    zone_high = float(candidate["high"])
    width = max(zone_high - zone_low, point)
    min_width = max(avg_range * LTF_IFVG_MIN_WIDTH_RATIO, point * LTF_IFVG_MIN_POINTS)
    result = {
        "valid": False,
        "mode": candidate["mode"],
        "low": zone_low,
        "high": zone_high,
        "width": width,
        "min_width": min_width,
        "source_index": candidate["source_index"],
        "origin_candle_index": candidate["origin_candle_index"],
        "origin_candle_high": candidate["origin_candle_high"],
        "origin_candle_low": candidate["origin_candle_low"],
        "entry_edge": zone_high if bias == "Long" else zone_low,
        "touch_index": None,
        "entry_distance": None,
        "entry_quality": None,
        "min_entry_quality": None,
        "clean_inversion": candidate["mode"] != "strict",
        "post_break_confirmed": False,
        "failure_reasons": [],
    }
    if width < min_width:
        result["failure_reasons"].append("width below minimum")
        return result

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

    result["entry_distance"] = entry_distance
    result["entry_quality"] = entry_quality

    touch_index = None
    clean_inversion = candidate["mode"] != "strict"
    post_break_confirmed = True
    effective_confirmation_index = confirmation_index
    if candidate["mode"] == "strict":
        clean_inversion, touch_index = is_clean_ifvg_inversion(
            rates,
            bias,
            candidate["source_index"],
            zone_low,
            zone_high,
            point,
        )
        effective_confirmation_index = touch_index
        post_break_confirmed = _has_meaningful_post_break_confirmation(
            rates,
            bias,
            effective_confirmation_index,
            zone_low,
            zone_high,
        )
    else:
        post_break_confirmed = _has_meaningful_post_break_confirmation(
            rates,
            bias,
            effective_confirmation_index,
            zone_low,
            zone_high,
        )

    min_entry_quality = (
        LTF_IFVG_ENTRY_MIN_QUALITY
        if candidate["mode"] == "strict"
        else LTF_IFVG_INTERNAL_MIN_ENTRY_QUALITY
    )
    result["touch_index"] = touch_index
    result["clean_inversion"] = clean_inversion
    result["post_break_confirmed"] = post_break_confirmed
    result["min_entry_quality"] = min_entry_quality

    if not clean_inversion:
        result["failure_reasons"].append("clean inversion failed")
    if not post_break_confirmed:
        result["failure_reasons"].append("post-break confirmation missing")
    if entry_quality < min_entry_quality:
        result["failure_reasons"].append("entry quality below minimum")

    valid = post_break_confirmed and clean_inversion and entry_quality >= min_entry_quality
    result["valid"] = valid
    return result
