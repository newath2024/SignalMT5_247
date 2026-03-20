from ..config.ltf import (
    EXTERNAL_LIQUIDITY_LEVELS,
    LTF_ALIGNED_SWEEP_DISPLACEMENT_MIN_QUALITY,
    LTF_ALIGNED_SWEEP_IFVG_MIN_QUALITY,
    LTF_ALIGNED_SWEEP_RECLAIM_MIN_QUALITY,
    LTF_COUNTERTREND_DISPLACEMENT_MIN_QUALITY,
    LTF_COUNTERTREND_IFVG_MIN_QUALITY,
    LTF_COUNTERTREND_SWEEP_MIN_QUALITY,
    LTF_IFVG_ARM_CONTEXT_BARS,
    LTF_IFVG_ARM_MIN_ORIGIN_BODY,
    LTF_IFVG_ARM_MIN_QUALITY,
    LTF_IFVG_ARM_MIN_WIDTH_RATIO,
    LTF_IFVG_ARM_MIN_WIDTH_TO_SPAN_RATIO,
    LTF_IFVG_ENTRY_MIN_QUALITY,
    LTF_POST_SWEEP_DISPLACEMENT_MAX_OPPOSITE_BARS,
    LTF_POST_SWEEP_DISPLACEMENT_MIN_BARS,
    LTF_POST_SWEEP_DISPLACEMENT_MIN_BODY,
    LTF_POST_SWEEP_DISPLACEMENT_MIN_DIRECTIONAL_RATIO,
    LTF_POST_SWEEP_DISPLACEMENT_MIN_MOVE_RATIO,
    LTF_POST_SWEEP_DISPLACEMENT_MIN_STRONG_BARS,
    LTF_RECLAIM_HOLD_BARS,
    LTF_RECLAIM_MIN_DISTANCE_RATIO,
    LTF_RECLAIM_MIN_QUALITY,
    LTF_RECLAIM_STRONG_QUALITY,
    LTF_SWEEP_LOOKBACK_HIGHS,
    LTF_SWEEP_LOOKBACK_LOWS,
    LTF_SWEEP_MIN_DEPTH_POINTS,
    LTF_SWEEP_MIN_DEPTH_RANGE_RATIO,
    LTF_SWEEP_QUALITY_BASE,
    LTF_SWEEP_QUALITY_DEPTH_SCALE,
    LTF_SWEEP_QUALITY_EXTERNAL_BONUS_CAP,
    LTF_SWEEP_QUALITY_EXTERNAL_BONUS_STEP,
    LTF_SWEEP_QUALITY_RECLAIM_BONUS,
    LTF_SWEEP_QUALITY_WICK_SCALE,
    LTF_SWEEP_SCAN_BARS,
    LTF_SWEEP_START_INDEX,
    WATCH_EXPIRY_BARS,
)
from ..patterns.ifvg import (
    find_first_touch_after_creation as detect_first_touch_after_creation,
    find_ifvg_zone as detect_ifvg_zone,
    is_clean_ifvg_inversion as validate_ifvg_inversion,
)
from ..utils import average_range, body_strength, clamp


def find_first_touch_after_creation(rates, source_index, zone_low, zone_high):
    return detect_first_touch_after_creation(rates, source_index, zone_low, zone_high)


def is_clean_ifvg_inversion(rates, bias, source_index, zone_low, zone_high, point):
    return validate_ifvg_inversion(rates, bias, source_index, zone_low, zone_high, point)


def find_ifvg_zone(rates, bias, sweep_index, mss_index, current_price, avg_range, point):
    return detect_ifvg_zone(
        rates,
        bias,
        sweep_index,
        mss_index,
        current_price,
        avg_range,
        point,
    )


def find_swept_external_liquidity(bias, sweep_high, sweep_low, sweep_close, reference_levels, point):
    swept = []
    for label in EXTERNAL_LIQUIDITY_LEVELS[bias]:
        level = reference_levels.get(label)
        if level is None:
            continue
        if bias == "Long":
            if sweep_low < level - point * 2 and sweep_close > level:
                swept.append(label)
        else:
            if sweep_high > level + point * 2 and sweep_close < level:
                swept.append(label)
    return swept


def detect_sweep_candidates(rates, bias, point, reference_levels):
    if rates is None or len(rates) < 30:
        return []

    avg_range = average_range(rates, 20)
    highs = rates["high"]
    lows = rates["low"]
    opens = rates["open"]
    closes = rates["close"]
    candidates = []
    start_index = max(LTF_SWEEP_START_INDEX, len(rates) - LTF_SWEEP_SCAN_BARS)

    for sweep_index in range(start_index, len(rates) - 2):
        prior_lows = lows[max(0, sweep_index - LTF_SWEEP_LOOKBACK_LOWS) : sweep_index]
        prior_highs = highs[max(0, sweep_index - LTF_SWEEP_LOOKBACK_HIGHS) : sweep_index]
        if len(prior_lows) < 6 or len(prior_highs) < 8:
            continue

        candle_range = max(float(highs[sweep_index] - lows[sweep_index]), point)
        sweep_high = float(highs[sweep_index])
        sweep_low = float(lows[sweep_index])
        sweep_close = float(closes[sweep_index])

        if bias == "Long":
            reference_low = float(prior_lows.min())
            sweep_depth = reference_low - sweep_low
            reclaim = sweep_close > reference_low
            wick_ratio = clamp(
                (min(opens[sweep_index], closes[sweep_index]) - lows[sweep_index]) / candle_range
            )
            structure_level = float(prior_highs.max())
            sweep_level = sweep_low
        else:
            reference_high = float(prior_highs.max())
            sweep_depth = sweep_high - reference_high
            reclaim = sweep_close < reference_high
            wick_ratio = clamp(
                (highs[sweep_index] - max(opens[sweep_index], closes[sweep_index])) / candle_range
            )
            structure_level = float(prior_lows.min())
            sweep_level = sweep_high

        if sweep_depth < max(avg_range * LTF_SWEEP_MIN_DEPTH_RANGE_RATIO, point * LTF_SWEEP_MIN_DEPTH_POINTS):
            continue
        if not reclaim:
            continue

        swept_external = find_swept_external_liquidity(
            bias,
            sweep_high,
            sweep_low,
            sweep_close,
            reference_levels,
            point,
        )
        if not swept_external:
            continue

        sweep_quality = clamp(
            LTF_SWEEP_QUALITY_BASE
            + clamp(sweep_depth / max(avg_range * 0.45, point * 4)) * LTF_SWEEP_QUALITY_DEPTH_SCALE
            + wick_ratio * LTF_SWEEP_QUALITY_WICK_SCALE
            + (LTF_SWEEP_QUALITY_RECLAIM_BONUS if reclaim else 0.0)
            + min(
                LTF_SWEEP_QUALITY_EXTERNAL_BONUS_CAP,
                LTF_SWEEP_QUALITY_EXTERNAL_BONUS_STEP * len(swept_external),
            )
        )

        candidates.append(
            {
                "bias": bias,
                "sweep_index": sweep_index,
                "sweep_level": sweep_level,
                "structure_level": structure_level,
                "sweep_quality": sweep_quality,
                "avg_range": avg_range,
                "swept_external": swept_external,
            }
        )

    return candidates


def evaluate_reclaim_quality(rates, bias, sweep_candidate, reference_levels, ifvg, point):
    swept_levels = [
        float(reference_levels[label])
        for label in sweep_candidate["swept_external"]
        if label in reference_levels
    ]
    if not swept_levels:
        return {"valid": False, "quality": 0.0}

    reclaimed_level = max(swept_levels) if bias == "Long" else min(swept_levels)
    reclaim_threshold = max(sweep_candidate["avg_range"] * LTF_RECLAIM_MIN_DISTANCE_RATIO, point * 2)
    sweep_index = sweep_candidate["sweep_index"]
    end_index = min(
        len(rates) - 1,
        max(sweep_index + LTF_RECLAIM_HOLD_BARS, ifvg["origin_candle_index"]),
    )
    closes = rates["close"][sweep_index : end_index + 1]
    if len(closes) == 0:
        return {"valid": False, "quality": 0.0}

    sweep_close = float(rates["close"][sweep_index])
    if bias == "Long":
        reclaim_distance = sweep_close - reclaimed_level
        hold_distance = float(closes.min()) - reclaimed_level
    else:
        reclaim_distance = reclaimed_level - sweep_close
        hold_distance = reclaimed_level - float(closes.max())

    quality = clamp(
        0.38
        + clamp(reclaim_distance / max(reclaim_threshold, point)) * 0.4
        + clamp(max(hold_distance, 0.0) / max(reclaim_threshold, point)) * 0.22
    )
    valid = reclaim_distance >= reclaim_threshold and hold_distance >= -point
    return {
        "valid": valid,
        "quality": quality,
        "reclaimed_level": reclaimed_level,
        "reclaim_distance": reclaim_distance,
        "hold_distance": hold_distance,
    }


def evaluate_post_sweep_displacement(rates, bias, sweep_candidate, ifvg, point):
    start_index = sweep_candidate["sweep_index"] + 1
    end_index = max(
        ifvg.get("touch_index") or ifvg["source_index"],
        ifvg["origin_candle_index"],
    )
    if end_index < start_index:
        return {"valid": False, "quality": 0.0}

    impulse = rates[start_index : end_index + 1]
    if len(impulse) < LTF_POST_SWEEP_DISPLACEMENT_MIN_BARS:
        return {"valid": False, "quality": 0.0}

    avg_range = sweep_candidate["avg_range"]
    ranges = [max(float(candle["high"] - candle["low"]), point) for candle in impulse]
    body_scores = [body_strength(candle, point) for candle in impulse]
    avg_body = sum(body_scores) / len(body_scores)

    if bias == "Long":
        directional_bars = sum(1 for candle in impulse if float(candle["close"]) > float(candle["open"]))
        strong_bars = sum(
            1
            for candle, body in zip(impulse, body_scores)
            if float(candle["close"]) > float(candle["open"]) and body >= LTF_POST_SWEEP_DISPLACEMENT_MIN_BODY
        )
        net_move = float(impulse["high"].max()) - float(rates["close"][sweep_candidate["sweep_index"]])
    else:
        directional_bars = sum(1 for candle in impulse if float(candle["close"]) < float(candle["open"]))
        strong_bars = sum(
            1
            for candle, body in zip(impulse, body_scores)
            if float(candle["close"]) < float(candle["open"]) and body >= LTF_POST_SWEEP_DISPLACEMENT_MIN_BODY
        )
        net_move = float(rates["close"][sweep_candidate["sweep_index"]]) - float(impulse["low"].min())

    opposite_bars = len(impulse) - directional_bars
    directional_ratio = directional_bars / len(impulse)
    efficiency = net_move / max(sum(ranges), point)
    move_ratio = net_move / max(avg_range, point)
    quality = clamp(
        0.36
        + clamp(move_ratio / max(LTF_POST_SWEEP_DISPLACEMENT_MIN_MOVE_RATIO * 1.5, 1e-9)) * 0.28
        + clamp(avg_body / max(LTF_POST_SWEEP_DISPLACEMENT_MIN_BODY, 1e-9)) * 0.2
        + clamp(efficiency / 0.6) * 0.16
    )
    valid = (
        strong_bars >= LTF_POST_SWEEP_DISPLACEMENT_MIN_STRONG_BARS
        and directional_ratio >= LTF_POST_SWEEP_DISPLACEMENT_MIN_DIRECTIONAL_RATIO
        and move_ratio >= LTF_POST_SWEEP_DISPLACEMENT_MIN_MOVE_RATIO
        and opposite_bars <= LTF_POST_SWEEP_DISPLACEMENT_MAX_OPPOSITE_BARS
        and efficiency >= 0.42
    )
    return {
        "valid": valid,
        "quality": quality,
        "bars": len(impulse),
        "strong_bars": strong_bars,
        "opposite_bars": opposite_bars,
        "directional_ratio": directional_ratio,
        "move_ratio": move_ratio,
        "efficiency": efficiency,
    }


def is_meaningful_watch_ifvg(rates, sweep_candidate, ifvg, point):
    width = float(ifvg["high"] - ifvg["low"])
    avg_range = sweep_candidate["avg_range"]
    min_width = max(avg_range * LTF_IFVG_ARM_MIN_WIDTH_RATIO, point * 4)
    if width < min_width:
        return {"valid": False, "quality": 0.0}

    origin_body = body_strength(rates[ifvg["origin_candle_index"]], point)
    context_start = max(sweep_candidate["sweep_index"], ifvg["source_index"] - LTF_IFVG_ARM_CONTEXT_BARS)
    context_end = min(len(rates) - 1, ifvg.get("touch_index") or ifvg["source_index"])
    context_span = max(
        float(rates["high"][context_start : context_end + 1].max() - rates["low"][context_start : context_end + 1].min()),
        point,
    )
    width_to_span = width / context_span
    quality = clamp(
        0.38
        + clamp(ifvg["quality"] / max(LTF_IFVG_ARM_MIN_QUALITY, 1e-9)) * 0.34
        + clamp(origin_body / max(LTF_IFVG_ARM_MIN_ORIGIN_BODY, 1e-9)) * 0.18
        + clamp(width_to_span / max(LTF_IFVG_ARM_MIN_WIDTH_TO_SPAN_RATIO, 1e-9)) * 0.1
    )
    valid = (
        ifvg["quality"] >= LTF_IFVG_ARM_MIN_QUALITY
        and origin_body >= LTF_IFVG_ARM_MIN_ORIGIN_BODY
        and width_to_span >= LTF_IFVG_ARM_MIN_WIDTH_TO_SPAN_RATIO
        and ifvg.get("post_break_confirmed", False)
    )
    return {
        "valid": valid,
        "quality": quality,
        "width_to_span": width_to_span,
        "origin_body": origin_body,
    }


def has_choppy_post_sweep_action(displacement):
    return (
        displacement["opposite_bars"] > LTF_POST_SWEEP_DISPLACEMENT_MAX_OPPOSITE_BARS
        or displacement["directional_ratio"] < LTF_POST_SWEEP_DISPLACEMENT_MIN_DIRECTIONAL_RATIO
        or displacement["efficiency"] < 0.42
    )


def classify_sweep_type(context, sweep_candidate, reclaim, displacement, ifvg_filter):
    structure_trend = context.get("structure_trend", "Range")
    continuation_risk = (
        (structure_trend == "Bullish" and sweep_candidate["bias"] == "Long")
        or (structure_trend == "Bearish" and sweep_candidate["bias"] == "Short")
    )
    countertrend = context.get("trend_alignment") == "countertrend"

    if not reclaim["valid"]:
        if countertrend:
            return {
                "type": "continuation",
                "reason": f"HTF {structure_trend.lower()}, {sweep_candidate['bias'].lower()} reclaim too weak",
            }
        return {"type": "continuation", "reason": "weak reclaim after sweep"}

    if not displacement["valid"]:
        return {"type": "continuation", "reason": "no post-sweep displacement"}

    if has_choppy_post_sweep_action(displacement):
        return {"type": "continuation", "reason": "choppy post-sweep action"}

    if not ifvg_filter["valid"]:
        return {"type": "continuation", "reason": "iFVG formed inside consolidation"}

    if countertrend:
        strong_countertrend = (
            sweep_candidate["sweep_quality"] >= LTF_COUNTERTREND_SWEEP_MIN_QUALITY
            and reclaim["quality"] >= LTF_RECLAIM_STRONG_QUALITY
            and displacement["quality"] >= LTF_COUNTERTREND_DISPLACEMENT_MIN_QUALITY
            and ifvg_filter["quality"] >= LTF_COUNTERTREND_IFVG_MIN_QUALITY
        )
        if not strong_countertrend:
            return {
                "type": "continuation",
                "reason": f"HTF {structure_trend.lower()}, {sweep_candidate['bias'].lower()} reclaim too weak",
            }

    if continuation_risk:
        strong_reversal = (
            reclaim["quality"] >= LTF_ALIGNED_SWEEP_RECLAIM_MIN_QUALITY
            and displacement["quality"] >= LTF_ALIGNED_SWEEP_DISPLACEMENT_MIN_QUALITY
            and ifvg_filter["quality"] >= LTF_ALIGNED_SWEEP_IFVG_MIN_QUALITY
            and displacement["strong_bars"] >= 2
        )
        if not strong_reversal:
            return {"type": "continuation", "reason": "continuation sweep"}

    if sweep_candidate["sweep_quality"] < 0.65 or reclaim["quality"] < LTF_RECLAIM_MIN_QUALITY:
        return {"type": "ambiguous", "reason": "reversal evidence too weak"}

    return {"type": "reversal", "reason": None}


def is_reversal_sweep(classification):
    return classification["type"] == "reversal"


def is_continuation_sweep(classification):
    return classification["type"] == "continuation"


def detect_ltf_watch_trigger(rates, bias, current_price, point, timeframe_name, reference_levels, context):
    candidates = []
    best_rejection = None
    best_rejection_score = -1.0

    for sweep_candidate in detect_sweep_candidates(rates, bias, point, reference_levels):
        ifvg = find_ifvg_zone(
            rates,
            bias,
            sweep_candidate["sweep_index"],
            len(rates) - 1,
            current_price,
            sweep_candidate["avg_range"],
            point,
        )
        if ifvg is None:
            rejection_reason = "no strict iFVG"
            rejection_score = sweep_candidate["sweep_quality"]
            if rejection_score > best_rejection_score:
                best_rejection = rejection_reason
                best_rejection_score = rejection_score
            continue
        if ifvg["mode"] != "strict" or ifvg["entry_quality"] < LTF_IFVG_ENTRY_MIN_QUALITY:
            rejection_reason = "iFVG not strict enough"
            rejection_score = sweep_candidate["sweep_quality"] + ifvg.get("quality", 0.0)
            if rejection_score > best_rejection_score:
                best_rejection = rejection_reason
                best_rejection_score = rejection_score
            continue
        if ifvg.get("touch_index") is None or ifvg["touch_index"] <= sweep_candidate["sweep_index"]:
            rejection_reason = "iFVG inversion not confirmed"
            rejection_score = sweep_candidate["sweep_quality"] + ifvg.get("quality", 0.0)
            if rejection_score > best_rejection_score:
                best_rejection = rejection_reason
                best_rejection_score = rejection_score
            continue

        reclaim = evaluate_reclaim_quality(rates, bias, sweep_candidate, reference_levels, ifvg, point)
        ifvg_filter = is_meaningful_watch_ifvg(rates, sweep_candidate, ifvg, point)
        displacement = evaluate_post_sweep_displacement(rates, bias, sweep_candidate, ifvg, point)
        classification = classify_sweep_type(
            context,
            sweep_candidate,
            reclaim,
            displacement,
            ifvg_filter,
        )
        if not is_reversal_sweep(classification):
            rejection_score = (
                sweep_candidate["sweep_quality"]
                + ifvg.get("quality", 0.0)
                + displacement.get("quality", 0.0)
                + reclaim.get("quality", 0.0)
            )
            if rejection_score > best_rejection_score:
                best_rejection = classification["reason"] or "continuation sweep"
                best_rejection_score = rejection_score
            continue

        watch_index = max(sweep_candidate["sweep_index"], ifvg["touch_index"])
        bars_since_watch = len(rates) - 1 - watch_index
        if bars_since_watch > WATCH_EXPIRY_BARS[timeframe_name]:
            rejection_reason = "watch expired before arm"
            rejection_score = (
                sweep_candidate["sweep_quality"]
                + ifvg.get("quality", 0.0)
                + displacement.get("quality", 0.0)
            )
            if rejection_score > best_rejection_score:
                best_rejection = rejection_reason
                best_rejection_score = rejection_score
            continue

        candidates.append(
            {
                **sweep_candidate,
                "ifvg": ifvg,
                "reclaim": reclaim,
                "displacement": displacement,
                "ifvg_filter": ifvg_filter,
                "sweep_classification": classification,
                "watch_index": watch_index,
                "bars_since_watch": bars_since_watch,
            }
        )

    if not candidates:
        return None, best_rejection

    candidates.sort(
        key=lambda item: (
            item["ifvg"]["entry_quality"]
            + item["ifvg"]["quality"]
            + item["sweep_quality"]
            + item["reclaim"]["quality"]
            + item["displacement"]["quality"],
            item["watch_index"],
        ),
        reverse=True,
    )
    return candidates[0], None
