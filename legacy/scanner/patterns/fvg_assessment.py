from __future__ import annotations

from ..config.htf import (
    HTF_BOS_CLOSE_BUFFER_POINTS,
    HTF_BOS_WICK_BUFFER_POINTS,
    HTF_FVG_BOS_BONUS,
    HTF_FVG_CLASS_BONUS,
    HTF_FVG_CONTEXT_MISSING_PENALTY,
    HTF_FVG_DEEP_MITIGATION_RATIO,
    HTF_FVG_DISPLACEMENT_BONUS,
    HTF_FVG_EXCEPTIONAL_MIN_QUALITY,
    HTF_FVG_FOLLOW_THROUGH_BARS,
    HTF_FVG_FOLLOW_THROUGH_BONUS,
    HTF_FVG_FULL_MITIGATION_RATIO,
    HTF_FVG_INVALIDATION_BUFFER,
    HTF_FVG_INVALIDATION_USE_CLOSE,
    HTF_FVG_KEEP_MIN_QUALITY,
    HTF_FVG_LOCATION_BONUS,
    HTF_FVG_MAX_IMMEDIATE_FILL_RATIO,
    HTF_FVG_MIN_FOLLOW_THROUGH_RANGE_RATIO,
    HTF_FVG_MIN_GAP_RATIO,
    HTF_FVG_MIN_POINTS,
    HTF_FVG_MIN_VISIBLE_RANGE_RATIO,
    HTF_FVG_MIN_WIDTH_TO_MOVE_RATIO,
    HTF_FVG_MITIGATION_PENALTY,
    HTF_FVG_PARTIAL_MITIGATION_RATIO,
    HTF_FVG_QUALITY_BASE,
    HTF_FVG_QUALITY_DIVISOR,
    HTF_FVG_QUALITY_SCALE,
    HTF_FVG_RANGE_PENALTY,
    HTF_FVG_SWEEP_BONUS,
    HTF_FVG_TIMEFRAME_BONUS,
    HTF_FVG_TRADABLE_MIN_QUALITY,
    HTF_FVG_TREND_ALIGNMENT_BONUS,
    HTF_SWEEP_BUFFER_POINTS,
)
from ..utils import clamp, zone_mid
from .displacement import displacement_strength
from .swings import (
    build_swing_structure,
    get_last_confirmed_swing_high_before,
    get_last_confirmed_swing_low_before,
    infer_trend_from_swings,
)


def _candidate_indexes(candidate: dict) -> tuple[int, int, int]:
    source_index = int(candidate["source_index"])
    start_index = int(candidate.get("start_index", max(0, source_index - 2)))
    middle_index = int(candidate.get("middle_index", max(0, source_index - 1)))
    return start_index, middle_index, source_index


def validate_fvg_geometry(candidate: dict, avg_range: float, point: float) -> dict:
    width = float(candidate["high"] - candidate["low"])
    min_width = max(float(avg_range) * HTF_FVG_MIN_GAP_RATIO, float(point) * HTF_FVG_MIN_POINTS)
    visible_threshold = max(float(avg_range) * HTF_FVG_MIN_VISIBLE_RANGE_RATIO, float(point) * HTF_FVG_MIN_POINTS)
    width_ratio = width / max(float(avg_range), float(point), 1e-9)
    return {
        "width": width,
        "min_width": min_width,
        "visible_threshold": visible_threshold,
        "width_ratio": width_ratio,
        "width_valid": width >= min_width,
        "visible": width >= visible_threshold,
        "valid": width >= min_width and width >= visible_threshold,
    }


def _assess_fvg_displacement(candidate: dict, rates, avg_range: float, point: float, geometry: dict) -> dict:
    _start_index, middle_index, source_index = _candidate_indexes(candidate)
    displacement = displacement_strength(
        rates,
        max(1, middle_index),
        source_index,
        candidate["bias"],
        avg_range,
        point,
    )
    if displacement is None:
        return {
            "valid": False,
            "formed_in_displacement": False,
            "strength": "weak",
            "net_move": 0.0,
            "directional_ratio": 0.0,
            "efficiency": 0.0,
            "avg_body": 0.0,
            "opposite_bars": 0,
            "weak_body_bars": 0,
            "width_to_move_ratio": 0.0,
            "visible_in_move": False,
            "debug_reason": "not enough candles to confirm displacement",
        }

    width_to_move_ratio = geometry["width"] / max(float(displacement["net_move"]), float(point), 1e-9)
    visible_in_move = width_to_move_ratio >= HTF_FVG_MIN_WIDTH_TO_MOVE_RATIO
    formed_in_displacement = bool(displacement["valid"]) and visible_in_move
    debug_reason = None
    if not displacement["valid"]:
        debug_reason = "gap did not form inside a valid displacement leg"
    elif not visible_in_move:
        debug_reason = "gap is too small relative to the displacement move"

    return {
        **displacement,
        "formed_in_displacement": formed_in_displacement,
        "width_to_move_ratio": width_to_move_ratio,
        "visible_in_move": visible_in_move,
        "debug_reason": debug_reason,
    }


def _find_fvg_bos(candidate: dict, rates, swings: dict, point: float) -> dict:
    start_index, middle_index, source_index = _candidate_indexes(candidate)
    highs = rates["high"]
    lows = rates["low"]
    closes = rates["close"]

    if candidate["bias"] == "Long":
        reference_swing = get_last_confirmed_swing_high_before(swings["highs"], start_index)
    else:
        reference_swing = get_last_confirmed_swing_low_before(swings["lows"], start_index)

    if reference_swing is None:
        return {"after_bos": False, "bos_index": None, "broken_swing": None}

    search_start = max(int(reference_swing["index"]) + 1, middle_index)
    search_end = min(len(rates) - 1, source_index + 1)
    for break_index in range(search_start, search_end + 1):
        if candidate["bias"] == "Long":
            close_break = float(closes[break_index]) > float(reference_swing["price"]) + point * HTF_BOS_CLOSE_BUFFER_POINTS
            wick_break = float(highs[break_index]) > float(reference_swing["price"]) + point * HTF_BOS_WICK_BUFFER_POINTS
        else:
            close_break = float(closes[break_index]) < float(reference_swing["price"]) - point * HTF_BOS_CLOSE_BUFFER_POINTS
            wick_break = float(lows[break_index]) < float(reference_swing["price"]) - point * HTF_BOS_WICK_BUFFER_POINTS

        if close_break and wick_break:
            return {
                "after_bos": True,
                "bos_index": break_index,
                "broken_swing": reference_swing,
            }

    return {
        "after_bos": False,
        "bos_index": None,
        "broken_swing": reference_swing,
    }


def _assess_fvg_sweep_context(candidate: dict, rates, swings: dict, point: float) -> dict:
    start_index, middle_index, source_index = _candidate_indexes(candidate)
    search_start = max(0, middle_index - 1)
    search_end = source_index
    closes = rates["close"]
    highs = rates["high"]
    lows = rates["low"]

    if candidate["bias"] == "Long":
        reference_swing = get_last_confirmed_swing_low_before(swings["lows"], start_index)
        if reference_swing is None:
            return {"near_liquidity_sweep": False, "sweep_index": None, "swept_swing": None}
        swept = None
        for index in range(search_start, search_end + 1):
            if float(lows[index]) < float(reference_swing["price"]) - point * HTF_SWEEP_BUFFER_POINTS:
                swept = index
                break
        reclaimed = swept is not None and float(closes[search_end]) >= float(reference_swing["price"])
    else:
        reference_swing = get_last_confirmed_swing_high_before(swings["highs"], start_index)
        if reference_swing is None:
            return {"near_liquidity_sweep": False, "sweep_index": None, "swept_swing": None}
        swept = None
        for index in range(search_start, search_end + 1):
            if float(highs[index]) > float(reference_swing["price"]) + point * HTF_SWEEP_BUFFER_POINTS:
                swept = index
                break
        reclaimed = swept is not None and float(closes[search_end]) <= float(reference_swing["price"])

    return {
        "near_liquidity_sweep": bool(swept is not None and reclaimed),
        "sweep_index": swept,
        "swept_swing": reference_swing,
    }


def _assess_fvg_location(candidate: dict, swings: dict, avg_range: float) -> dict:
    source_index = int(candidate["source_index"])
    range_high = get_last_confirmed_swing_high_before(swings["highs"], source_index, require_significant=False)
    range_low = get_last_confirmed_swing_low_before(swings["lows"], source_index, require_significant=False)
    if range_high is None or range_low is None:
        return {
            "location_in_range": "unknown",
            "location_ratio": None,
            "location_favorable": False,
        }

    dealing_range = float(range_high["price"] - range_low["price"])
    if dealing_range <= max(float(avg_range), 1e-9):
        return {
            "location_in_range": "unknown",
            "location_ratio": None,
            "location_favorable": False,
        }

    ratio = clamp((zone_mid(candidate) - float(range_low["price"])) / max(dealing_range, 1e-9))
    if ratio <= 0.35:
        location = "discount"
    elif ratio >= 0.65:
        location = "premium"
    else:
        location = "equilibrium"

    location_favorable = (
        (candidate["bias"] == "Long" and location == "discount")
        or (candidate["bias"] == "Short" and location == "premium")
    )
    return {
        "location_in_range": location,
        "location_ratio": ratio,
        "location_favorable": location_favorable,
    }


def assess_fvg_context(candidate: dict, rates, avg_range: float, point: float, swings: dict | None = None) -> dict:
    if swings is None:
        swings = build_swing_structure(rates, avg_range)

    source_index = int(candidate["source_index"])
    trend = infer_trend_from_swings(swings["highs"], swings["lows"], source_index)
    trend_aligned = (
        (candidate["bias"] == "Long" and trend == "Bullish")
        or (candidate["bias"] == "Short" and trend == "Bearish")
    )
    bos = _find_fvg_bos(candidate, rates, swings, point)
    sweep = _assess_fvg_sweep_context(candidate, rates, swings, point)
    location = _assess_fvg_location(candidate, swings, avg_range)

    has_context = bool(
        bos["after_bos"]
        or sweep["near_liquidity_sweep"]
        or trend_aligned
        or location["location_favorable"]
    )

    return {
        "trend": trend,
        "trend_aligned": trend_aligned,
        "after_bos": bos["after_bos"],
        "bos_index": bos["bos_index"],
        "broken_swing": bos["broken_swing"],
        "near_liquidity_sweep": sweep["near_liquidity_sweep"],
        "sweep_index": sweep["sweep_index"],
        "swept_swing": sweep["swept_swing"],
        "location_in_range": location["location_in_range"],
        "location_ratio": location["location_ratio"],
        "location_favorable": location["location_favorable"],
        "has_context": has_context,
        "context_signals": sum(
            1
            for flag in (
                bos["after_bos"],
                sweep["near_liquidity_sweep"],
                trend_aligned,
                location["location_favorable"],
            )
            if flag
        ),
    }


def evaluate_fvg_follow_through(candidate: dict, rates, avg_range: float, point: float) -> dict:
    source_index = int(candidate["source_index"])
    future_start = source_index + 1
    future_end = min(len(rates) - 1, source_index + HTF_FVG_FOLLOW_THROUGH_BARS)
    width = max(float(candidate["high"] - candidate["low"]), float(point), 1e-9)
    if future_start > future_end:
        return {
            "confirmed": False,
            "strength": "weak",
            "continuation_move": 0.0,
            "directional_ratio": 0.0,
            "immediate_fill_ratio": 0.0,
            "debug_reason": "no closed follow-through bars after FVG formation",
        }

    future = rates[future_start : future_end + 1]
    closes = future["close"]
    opens = future["open"]
    highs = future["high"]
    lows = future["low"]
    required_move = max(float(avg_range) * HTF_FVG_MIN_FOLLOW_THROUGH_RANGE_RATIO, width * 0.5, float(point) * 4)
    immediate_window_end = min(len(rates) - 1, source_index + min(2, HTF_FVG_FOLLOW_THROUGH_BARS))
    immediate_window = rates[future_start : immediate_window_end + 1]

    if candidate["bias"] == "Long":
        continuation_move = float(highs.max()) - float(rates["high"][source_index])
        directional_bars = sum(1 for close_value, open_value in zip(closes, opens) if float(close_value) > float(open_value))
        immediate_fill_ratio = clamp(
            (float(candidate["high"]) - float(immediate_window["low"].min())) / width,
            low=0.0,
            high=2.0,
        )
    else:
        continuation_move = float(rates["low"][source_index]) - float(lows.min())
        directional_bars = sum(1 for close_value, open_value in zip(closes, opens) if float(close_value) < float(open_value))
        immediate_fill_ratio = clamp(
            (float(immediate_window["high"].max()) - float(candidate["low"])) / width,
            low=0.0,
            high=2.0,
        )

    directional_ratio = directional_bars / max(len(future), 1)
    confirmed = continuation_move >= required_move and directional_ratio >= 0.5
    if immediate_fill_ratio >= HTF_FVG_MAX_IMMEDIATE_FILL_RATIO:
        confirmed = False

    if confirmed and continuation_move >= required_move * 1.5 and directional_ratio >= 0.66 and immediate_fill_ratio <= 0.25:
        strength = "strong"
        debug_reason = None
    elif confirmed:
        strength = "moderate"
        debug_reason = None
    else:
        strength = "weak"
        debug_reason = "post-formation continuation was too weak or the gap was filled too quickly"

    return {
        "confirmed": confirmed,
        "strength": strength,
        "continuation_move": continuation_move,
        "directional_ratio": directional_ratio,
        "immediate_fill_ratio": immediate_fill_ratio,
        "required_move": required_move,
        "debug_reason": debug_reason,
    }


def get_fvg_mitigation_status(candidate: dict, rates) -> dict:
    source_index = int(candidate["source_index"])
    after = rates[source_index + 1 :]
    width = max(float(candidate["high"] - candidate["low"]), 1e-9)
    low = float(candidate["low"])
    high = float(candidate["high"])
    buffer = float(HTF_FVG_INVALIDATION_BUFFER or 0.0)

    if len(after) == 0:
        return {
            "status": "untouched",
            "fill_ratio": 0.0,
            "max_fill_ratio": 0.0,
            "touched": False,
            "usable": True,
            "invalidated": False,
        }

    if candidate["bias"] == "Long":
        min_low = float(after["low"].min())
        fill_ratio = clamp((high - min_low) / width, low=0.0, high=2.0)
        touched = min_low <= high
        if HTF_FVG_INVALIDATION_USE_CLOSE:
            invalidated = bool((after["close"] < low - buffer).any())
        else:
            invalidated = bool((after["low"] < low - buffer).any())
    else:
        max_high = float(after["high"].max())
        fill_ratio = clamp((max_high - low) / width, low=0.0, high=2.0)
        touched = max_high >= low
        if HTF_FVG_INVALIDATION_USE_CLOSE:
            invalidated = bool((after["close"] > high + buffer).any())
        else:
            invalidated = bool((after["high"] > high + buffer).any())

    if invalidated:
        status = "invalidated"
    elif fill_ratio >= HTF_FVG_FULL_MITIGATION_RATIO:
        status = "filled"
    elif fill_ratio >= HTF_FVG_DEEP_MITIGATION_RATIO:
        status = "deep_mitigated"
    elif touched and fill_ratio >= HTF_FVG_PARTIAL_MITIGATION_RATIO:
        status = "partially_mitigated"
    elif touched:
        status = "partially_mitigated"
    else:
        status = "untouched"

    return {
        "status": status,
        "fill_ratio": fill_ratio,
        "max_fill_ratio": fill_ratio,
        "touched": touched,
        "usable": status not in {"filled", "invalidated"},
        "invalidated": invalidated,
    }


def classify_fvg(candidate: dict, context: dict, displacement: dict, follow_through: dict) -> str:
    if not displacement["formed_in_displacement"] or follow_through["strength"] == "weak":
        return "weak_fvg"
    if context["after_bos"] and displacement["strength"] == "strong" and follow_through["strength"] == "strong":
        return "impulse_fvg"
    if context["near_liquidity_sweep"]:
        return "sweep_fvg"
    if context["trend_aligned"] and context["location_favorable"]:
        return "trend_fvg"
    if context["location_in_range"] == "equilibrium" or not context["has_context"]:
        return "internal_fvg"
    return "weak_fvg"


def compute_fvg_quality(
    candidate: dict,
    timeframe_name: str,
    avg_range: float,
    point: float,
    geometry: dict,
    displacement: dict,
    context: dict,
    follow_through: dict,
    mitigation: dict,
    fvg_class: str,
) -> dict:
    width_component = clamp(
        geometry["width"] / max(float(avg_range) * HTF_FVG_QUALITY_DIVISOR, float(point) * HTF_FVG_MIN_POINTS, 1e-9)
    ) * HTF_FVG_QUALITY_SCALE
    components = {
        "base": HTF_FVG_QUALITY_BASE,
        "timeframe": HTF_FVG_TIMEFRAME_BONUS[timeframe_name],
        "width": width_component,
        "displacement": HTF_FVG_DISPLACEMENT_BONUS.get(displacement["strength"], 0.0),
        "bos": HTF_FVG_BOS_BONUS if context["after_bos"] else 0.0,
        "liquidity_sweep": HTF_FVG_SWEEP_BONUS if context["near_liquidity_sweep"] else 0.0,
        "trend_alignment": HTF_FVG_TREND_ALIGNMENT_BONUS if context["trend_aligned"] else 0.0,
        "location": HTF_FVG_LOCATION_BONUS.get(context["location_in_range"], 0.0),
        "follow_through": HTF_FVG_FOLLOW_THROUGH_BONUS.get(follow_through["strength"], 0.0),
        "class_bonus": HTF_FVG_CLASS_BONUS.get(fvg_class, 0.0),
    }
    penalties = {}
    if not context["has_context"]:
        penalties["missing_context"] = HTF_FVG_CONTEXT_MISSING_PENALTY
    if context["location_in_range"] == "equilibrium":
        penalties["mid_range"] = HTF_FVG_RANGE_PENALTY
    mitigation_penalty = HTF_FVG_MITIGATION_PENALTY.get(mitigation["status"], 0.0)
    if mitigation_penalty:
        penalties["mitigation"] = mitigation_penalty

    raw_score = sum(float(value) for value in components.values()) - sum(float(value) for value in penalties.values())
    return {
        "quality": clamp(raw_score),
        "components": {key: round(float(value), 4) for key, value in components.items()},
        "penalties": {key: round(float(value), 4) for key, value in penalties.items()},
    }


def _rejection_reason(
    geometry: dict,
    displacement: dict,
    context: dict,
    follow_through: dict,
    mitigation: dict,
    quality: float,
    tradable: bool,
    keep: bool,
) -> str | None:
    if not geometry["width_valid"]:
        return "FVG width is below the minimum HTF gap threshold"
    if not geometry["visible"]:
        return "FVG is too small relative to the current HTF dealing range"
    if mitigation["status"] == "invalidated":
        return "FVG has already been invalidated after formation"
    if mitigation["status"] == "filled":
        return "FVG has already been fully mitigated"
    if not displacement["formed_in_displacement"]:
        return displacement["debug_reason"] or "FVG did not form inside a meaningful displacement leg"
    if follow_through["strength"] == "weak":
        return follow_through["debug_reason"] or "FVG did not receive enough continuation after creation"
    if not tradable and not context["has_context"] and quality < HTF_FVG_EXCEPTIONAL_MIN_QUALITY:
        return "FVG lacks structural context and is not strong enough to override that"
    if not keep:
        return "FVG quality fell below the HTF keep threshold"
    return None


def assess_fvg_candidate(candidate: dict, rates, timeframe_name: str, avg_range: float, point: float, swings: dict | None = None) -> dict:
    if swings is None:
        swings = build_swing_structure(rates, avg_range)

    geometry = validate_fvg_geometry(candidate, avg_range, point)
    displacement = _assess_fvg_displacement(candidate, rates, avg_range, point, geometry)
    context = assess_fvg_context(candidate, rates, avg_range, point, swings=swings)
    follow_through = evaluate_fvg_follow_through(candidate, rates, avg_range, point)
    mitigation = get_fvg_mitigation_status(candidate, rates)
    fvg_class = classify_fvg(candidate, context, displacement, follow_through)
    quality_payload = compute_fvg_quality(
        candidate,
        timeframe_name,
        avg_range,
        point,
        geometry,
        displacement,
        context,
        follow_through,
        mitigation,
        fvg_class,
    )

    valid = bool(geometry["valid"]) and mitigation["status"] not in {"filled", "invalidated"}
    tradable = (
        valid
        and displacement["formed_in_displacement"]
        and follow_through["confirmed"]
        and quality_payload["quality"] >= HTF_FVG_TRADABLE_MIN_QUALITY
        and (
            context["has_context"]
            or quality_payload["quality"] >= HTF_FVG_EXCEPTIONAL_MIN_QUALITY
        )
        and fvg_class != "weak_fvg"
    )
    keep = (
        valid
        and mitigation["usable"]
        and quality_payload["quality"] >= HTF_FVG_KEEP_MIN_QUALITY
        and (
            follow_through["strength"] != "weak"
            or quality_payload["quality"] >= HTF_FVG_EXCEPTIONAL_MIN_QUALITY
        )
    )
    rejection_reason = _rejection_reason(
        geometry,
        displacement,
        context,
        follow_through,
        mitigation,
        quality_payload["quality"],
        tradable,
        keep,
    )

    return {
        "valid": valid,
        "tradable": tradable,
        "keep": keep,
        "formed_in_displacement": displacement["formed_in_displacement"],
        "displacement_strength": displacement["strength"],
        "after_bos": context["after_bos"],
        "near_liquidity_sweep": context["near_liquidity_sweep"],
        "trend": context["trend"],
        "trend_aligned": context["trend_aligned"],
        "location_in_range": context["location_in_range"],
        "fvg_class": fvg_class,
        "mitigation_status": mitigation["status"],
        "mitigation_ratio": mitigation["fill_ratio"],
        "follow_through_strength": follow_through["strength"],
        "follow_through_confirmed": follow_through["confirmed"],
        "follow_through_fill_ratio": follow_through["immediate_fill_ratio"],
        "width": geometry["width"],
        "width_ratio": geometry["width_ratio"],
        "visible": geometry["visible"],
        "quality": quality_payload["quality"],
        "quality_components": quality_payload["components"],
        "quality_penalties": quality_payload["penalties"],
        "rejection_reason": rejection_reason,
        "bos_index": context["bos_index"],
        "sweep_index": context["sweep_index"],
        "context_signals": context["context_signals"],
        "debug": {
            "geometry": geometry,
            "displacement": displacement,
            "context": context,
            "follow_through": follow_through,
            "mitigation": mitigation,
        },
    }
