from __future__ import annotations

from ..config.htf import (
    HTF_BOS_CLOSE_BUFFER_POINTS,
    HTF_COMPOSITE_DISTANCE_WEIGHT,
    HTF_LIQUIDITY_DIRECTIONAL_SCORE_PENALTY,
    HTF_LIQUIDITY_CONFIRMATION_BARS,
    HTF_LIQUIDITY_NEUTRAL_SCORE_PENALTY,
    HTF_LIQUIDITY_RECENT_BARS,
    HTF_REACTION_NEAR,
    HTF_REACTION_NEAR_WITH_BODY,
    HTF_REACTION_RESPECTED,
    HTF_REACTION_STRONG,
    HTF_SWEEP_BUFFER_POINTS,
    HTF_TOLERANCE_AVG_H1_RATIO,
    HTF_TOLERANCE_MIN_POINTS,
)
from ..patterns.displacement import displacement_strength
from ..structure.swings import (
    build_swing_structure,
    get_last_confirmed_swing_high_before,
    get_last_confirmed_swing_low_before,
)
from ..utils import average_range, clamp

LIQUIDITY_LEVEL_TYPES = {
    "Previous Day High",
    "Previous Day Low",
    "Previous Week High",
    "Previous Week Low",
    "Asia Session High",
    "Asia Session Low",
    "London Session High",
    "London Session Low",
}


def is_liquidity_level(zone) -> bool:
    if zone is None:
        return False
    if zone.get("is_liquidity_level"):
        return True
    return str(zone.get("type") or zone.get("label") or "") in LIQUIDITY_LEVEL_TYPES


def liquidity_level_side(zone) -> str | None:
    zone_type = str(zone.get("type") or zone.get("label") or "").lower()
    if "low" in zone_type:
        return "low"
    if "high" in zone_type:
        return "high"
    return None


def liquidity_level_value(zone) -> float | None:
    value = zone.get("liquidity_level")
    if value is None:
        low = zone.get("low")
        high = zone.get("high")
        if low is None and high is None:
            return None
        if low is None:
            value = high
        elif high is None:
            value = low
        else:
            value = (float(low) + float(high)) / 2.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def liquidity_interaction_label(state: str | None, label: str) -> str:
    if state == "swept_and_reclaimed":
        return f"Sweep + reclaim at {label}"
    if state == "swept":
        return f"Swept {label}"
    if state == "tapped":
        return f"Tapped {label}"
    return f"At {label}"


def reaction_strength_label(reaction: float | None) -> str:
    value = float(reaction or 0.0)
    if value >= HTF_REACTION_STRONG:
        return "strong"
    if value >= HTF_REACTION_RESPECTED:
        return "moderate"
    if value >= HTF_REACTION_NEAR:
        return "light"
    return "none"


def _liquidity_tolerance(zone, avg_h1: float, point: float) -> float:
    explicit = float(zone.get("tolerance") or 0.0)
    return max(
        explicit,
        avg_h1 * HTF_TOLERANCE_AVG_H1_RATIO,
        point * HTF_TOLERANCE_MIN_POINTS,
    )


def _liquidity_recent_slice(zone, rates_h1):
    recent_bars = int(HTF_LIQUIDITY_RECENT_BARS.get(zone.get("timeframe"), HTF_LIQUIDITY_RECENT_BARS["D1"]))
    start_index = max(0, len(rates_h1) - recent_bars)
    return start_index, rates_h1[start_index:]


def _touched_level(level: float, side: str, candle_high: float, candle_low: float, tolerance: float) -> bool:
    if side == "low":
        return candle_low <= level + tolerance
    return candle_high >= level - tolerance


def _swept_level(level: float, side: str, candle_high: float, candle_low: float, sweep_buffer: float) -> bool:
    if side == "low":
        return candle_low < level - sweep_buffer
    return candle_high > level + sweep_buffer


def _reclaimed_level(level: float, side: str, close_value: float) -> bool:
    if side == "low":
        return close_value >= level
    return close_value <= level


def _find_reclaim_index(rates_h1, level: float, side: str, sweep_index: int | None) -> int | None:
    if sweep_index is None:
        return None
    closes = rates_h1["close"]
    for index in range(sweep_index, len(rates_h1)):
        if _reclaimed_level(level, side, float(closes[index])):
            return index
    return None


def _assess_liquidity_mss(rates_h1, avg_h1: float, point: float, bias: str, sweep_index: int, reclaim_index: int | None) -> dict:
    swings = build_swing_structure(rates_h1, avg_h1)
    break_index = None
    reference_swing = None
    closes = rates_h1["close"]
    search_start = max(sweep_index + 1, (reclaim_index or sweep_index) + 1)

    if bias == "Long":
        reference_swing = get_last_confirmed_swing_high_before(swings["highs"], sweep_index, require_significant=False)
        if reference_swing is not None:
            threshold = float(reference_swing["price"]) + point * HTF_BOS_CLOSE_BUFFER_POINTS
            for index in range(search_start, len(rates_h1)):
                if float(closes[index]) > threshold:
                    break_index = index
                    break
    else:
        reference_swing = get_last_confirmed_swing_low_before(swings["lows"], sweep_index, require_significant=False)
        if reference_swing is not None:
            threshold = float(reference_swing["price"]) - point * HTF_BOS_CLOSE_BUFFER_POINTS
            for index in range(search_start, len(rates_h1)):
                if float(closes[index]) < threshold:
                    break_index = index
                    break

    return {
        "confirmed": break_index is not None,
        "break_index": break_index,
        "reference_swing": reference_swing,
    }


def _assess_liquidity_displacement(
    rates_h1,
    avg_h1: float,
    point: float,
    bias: str,
    sweep_index: int,
    reclaim_index: int | None,
) -> dict | None:
    impulse_start = max(1, reclaim_index if reclaim_index is not None else sweep_index + 1)
    impulse_end = min(len(rates_h1) - 1, impulse_start + HTF_LIQUIDITY_CONFIRMATION_BARS - 1)
    if impulse_end - impulse_start + 1 < 2:
        return None
    return displacement_strength(rates_h1, impulse_start, impulse_end, bias, avg_h1, point)


def _trend_alignment(structure: dict, bias: str | None) -> str:
    trend = structure.get("trend") if structure else "Range"
    if bias not in {"Long", "Short"}:
        return "liquidity_only"
    if trend == "Bullish":
        return "aligned" if bias == "Long" else "countertrend"
    if trend == "Bearish":
        return "aligned" if bias == "Short" else "countertrend"
    return "range"


def evaluate_liquidity_level(zone, snapshot, structure=None):
    rates_h1 = snapshot["rates"]["H1"]
    point = float(snapshot["point"])
    price = float(snapshot["current_price"])
    avg_h1 = average_range(rates_h1, 20)
    level = liquidity_level_value(zone)
    side = liquidity_level_side(zone)

    if level is None or side is None or len(rates_h1) == 0:
        return {
            "zone": zone,
            "bias": "Neutral",
            "market_structure_bias": "Neutral",
            "zone_quality": float(zone.get("quality") or 0.0),
            "reaction_clarity": 0.0,
            "reaction_strength": "none",
            "distance_score": 0.0,
            "structure_trend": (structure or {}).get("trend", "Range"),
            "trend_alignment": "liquidity_only",
            "clear": False,
            "score": -1.0,
            "valid": False,
            "invalidation_reason": "liquidity level metadata incomplete",
            "liquidity_interaction_state": "untouched",
            "liquidity_interaction_label": str(zone.get("label") or "Liquidity level"),
            "is_liquidity_level": True,
        }

    tolerance = _liquidity_tolerance(zone, avg_h1, point)
    sweep_buffer = point * HTF_SWEEP_BUFFER_POINTS
    start_index, recent = _liquidity_recent_slice(zone, rates_h1)
    touched_indices = []
    swept_indices = []

    for offset in range(len(recent)):
        index = start_index + offset
        candle_high = float(recent["high"][offset])
        candle_low = float(recent["low"][offset])
        if _touched_level(level, side, candle_high, candle_low, tolerance):
            touched_indices.append(index)
        if _swept_level(level, side, candle_high, candle_low, sweep_buffer):
            swept_indices.append(index)

    tap_index = touched_indices[-1] if touched_indices else None
    sweep_index = swept_indices[-1] if swept_indices else None
    reclaim_index = _find_reclaim_index(rates_h1, level, side, sweep_index)
    last_open = float(rates_h1["open"][-1])
    last_close = float(rates_h1["close"][-1])
    reclaimed = reclaim_index is not None and _reclaimed_level(level, side, last_close)
    at_level = abs(price - level) <= tolerance

    if sweep_index is not None and reclaimed:
        interaction_state = "swept_and_reclaimed"
    elif sweep_index is not None:
        interaction_state = "swept"
    elif tap_index is not None:
        interaction_state = "tapped"
    else:
        interaction_state = "untouched"

    directional_body = last_close > last_open if side == "low" else last_close < last_open
    reaction = 0.0
    market_structure_bias = "Neutral"
    structure_confirmation_reason = None
    displacement = None
    mss = {"confirmed": False, "break_index": None, "reference_swing": None}

    if interaction_state == "swept_and_reclaimed":
        candidate_bias = "Long" if side == "low" else "Short"
        displacement = _assess_liquidity_displacement(rates_h1, avg_h1, point, candidate_bias, sweep_index, reclaim_index)
        mss = _assess_liquidity_mss(rates_h1, avg_h1, point, candidate_bias, sweep_index, reclaim_index)

        confirmations = []
        if displacement and displacement.get("valid"):
            confirmations.append("sweep + displacement")
        if mss["confirmed"]:
            confirmations.append("sweep + MSS")
        if confirmations:
            market_structure_bias = candidate_bias
            structure_confirmation_reason = " + ".join(confirmations)
            reaction = HTF_REACTION_STRONG
        else:
            reaction = HTF_REACTION_RESPECTED
    elif interaction_state == "swept":
        reaction = HTF_REACTION_NEAR_WITH_BODY if directional_body else HTF_REACTION_NEAR
    elif interaction_state == "tapped":
        reaction = HTF_REACTION_NEAR_WITH_BODY if directional_body else HTF_REACTION_NEAR
    elif at_level:
        reaction = HTF_REACTION_NEAR

    distance_score = clamp(1.0 - abs(price - level) / max(tolerance, point))
    trend = (structure or {}).get("trend", "Range")
    trend_alignment = _trend_alignment(structure or {}, market_structure_bias)
    sweep_active = interaction_state in {"swept", "swept_and_reclaimed"}
    clear = sweep_active

    composite = float(zone.get("quality") or 0.0) + reaction + distance_score * HTF_COMPOSITE_DISTANCE_WEIGHT
    if interaction_state == "swept":
        composite += 0.04
    elif interaction_state == "swept_and_reclaimed":
        composite += 0.08
    if market_structure_bias in {"Long", "Short"}:
        composite += 0.12
        composite -= HTF_LIQUIDITY_DIRECTIONAL_SCORE_PENALTY
    else:
        composite -= HTF_LIQUIDITY_NEUTRAL_SCORE_PENALTY
    if trend_alignment == "aligned":
        composite += 0.05
    elif trend_alignment == "countertrend":
        composite -= 0.08

    debug = [
        f"level={level:.5f}",
        f"tolerance={tolerance:.5f}",
        f"state={interaction_state}",
        f"distance_score={distance_score:.2f}",
    ]
    if sweep_index is not None:
        debug.append(f"sweep_index={sweep_index}")
    if reclaim_index is not None:
        debug.append(f"reclaim_index={reclaim_index}")
    if displacement:
        debug.append(f"displacement={displacement.get('strength')}/{bool(displacement.get('valid'))}")
    if mss["confirmed"]:
        debug.append(f"mss_index={mss['break_index']}")

    return {
        "zone": zone,
        "bias": market_structure_bias,
        "market_structure_bias": market_structure_bias,
        "zone_quality": float(zone.get("quality") or 0.0),
        "reaction_clarity": reaction,
        "reaction_strength": reaction_strength_label(reaction),
        "distance_score": distance_score,
        "structure_trend": trend,
        "trend_alignment": trend_alignment,
        "clear": clear,
        "score": composite,
        "valid": True,
        "invalidation_reason": None,
        "liquidity_interaction_state": interaction_state,
        "liquidity_interaction_label": liquidity_interaction_label(
            interaction_state,
            str(zone.get("label") or "Liquidity level"),
        ),
        "is_liquidity_level": True,
        "liquidity_level": level,
        "liquidity_tolerance": tolerance,
        "tap_index": tap_index,
        "sweep_index": sweep_index,
        "reclaim_index": reclaim_index,
        "reclaimed": reclaimed,
        "displacement_confirmed": bool(displacement and displacement.get("valid")),
        "mss_confirmed": bool(mss["confirmed"]),
        "mss_index": mss["break_index"],
        "structure_confirmation_reason": structure_confirmation_reason,
        "liquidity_debug": "; ".join(debug),
    }
