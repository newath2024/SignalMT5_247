from ..config.htf import (
    HTF_OB_FVG_MODE,
    HTF_OB_FVG_PENALTY,
    HTF_OB_MIN_BODY_RATIO,
    HTF_OB_MIN_DISPLACEMENT_RATIO,
    HTF_OB_USE_STRICT_BODY_ENGULF,
    HTF_ORDER_BLOCK_BOS_BONUS,
    HTF_ORDER_BLOCK_DISPLACEMENT_BONUS,
    HTF_ORDER_BLOCK_FVG_BONUS,
    HTF_ORDER_BLOCK_MAX_ZONES,
    HTF_ORDER_BLOCK_MIN_BARS,
    HTF_ORDER_BLOCK_QUALITY_BASE,
    HTF_ORDER_BLOCK_QUALITY_SCALE,
    HTF_ORDER_BLOCK_SCAN_START,
    HTF_ORDER_BLOCK_SWEEP_BONUS,
    HTF_ORDER_BLOCK_TIMEFRAME_BONUS,
    HTF_ORDER_BLOCK_TREND_ALIGNMENT_BONUS,
    HTF_SWING_MIN_RANGE_RATIO,
    HTF_SWING_STRENGTH,
)
from ..utils import body_strength, clamp
from .fvg import has_impulse_fvg
from .swings import build_swing_structure, infer_trend_from_swings
from .validators import is_valid_ob


def _ob_fvg_mode():
    mode = str(HTF_OB_FVG_MODE or "medium").strip().lower()
    return mode if mode in {"strict", "medium"} else "medium"


def _body_size(rates, index):
    return abs(float(rates["close"][index]) - float(rates["open"][index]))


def _body_ratio(rates, index, point):
    candle = {
        "open": float(rates["open"][index]),
        "high": float(rates["high"][index]),
        "low": float(rates["low"][index]),
        "close": float(rates["close"][index]),
    }
    return body_strength(candle, max(float(point or 0.0), 1e-9))


def _engulfing_displacement_ratio(rates, index, avg_range, point):
    if avg_range is None or float(avg_range) <= 0:
        return None
    baseline = max(float(avg_range), float(point or 0.0), 1e-9)
    return _body_size(rates, index) / baseline


def is_bullish_engulfing(rates, prev_index, curr_index, strict_body=HTF_OB_USE_STRICT_BODY_ENGULF):
    prev_open = float(rates["open"][prev_index])
    prev_close = float(rates["close"][prev_index])
    curr_open = float(rates["open"][curr_index])
    curr_close = float(rates["close"][curr_index])

    if prev_close >= prev_open or curr_close <= curr_open:
        return False

    if strict_body:
        return curr_open <= prev_close and curr_close >= prev_open

    prev_low = float(rates["low"][prev_index])
    prev_high = float(rates["high"][prev_index])
    curr_low = float(rates["low"][curr_index])
    curr_high = float(rates["high"][curr_index])
    return curr_low <= prev_low and curr_high >= prev_high


def is_bearish_engulfing(rates, prev_index, curr_index, strict_body=HTF_OB_USE_STRICT_BODY_ENGULF):
    prev_open = float(rates["open"][prev_index])
    prev_close = float(rates["close"][prev_index])
    curr_open = float(rates["open"][curr_index])
    curr_close = float(rates["close"][curr_index])

    if prev_close <= prev_open or curr_close >= curr_open:
        return False

    if strict_body:
        return curr_open >= prev_close and curr_close <= prev_open

    prev_low = float(rates["low"][prev_index])
    prev_high = float(rates["high"][prev_index])
    curr_low = float(rates["low"][curr_index])
    curr_high = float(rates["high"][curr_index])
    return curr_low <= prev_low and curr_high >= prev_high


def _passes_candidate_quality_filters(rates, source_index, engulf_index, avg_range, point):
    source_body_ratio = _body_ratio(rates, source_index, point)
    engulf_body_ratio = _body_ratio(rates, engulf_index, point)
    if source_body_ratio < HTF_OB_MIN_BODY_RATIO or engulf_body_ratio < HTF_OB_MIN_BODY_RATIO:
        return False, source_body_ratio, engulf_body_ratio, None

    displacement_ratio = _engulfing_displacement_ratio(rates, engulf_index, avg_range, point)
    if displacement_ratio is not None and displacement_ratio < HTF_OB_MIN_DISPLACEMENT_RATIO:
        return False, source_body_ratio, engulf_body_ratio, displacement_ratio

    return True, source_body_ratio, engulf_body_ratio, displacement_ratio


def _build_ob_candidate(
    rates,
    source_index,
    engulf_index,
    bias,
    ob_type,
    strict_body,
    source_body_ratio,
    engulf_body_ratio,
    displacement_ratio,
):
    source_open = float(rates["open"][source_index])
    source_high = float(rates["high"][source_index])
    source_low = float(rates["low"][source_index])
    zone_low = source_low if bias == "Long" else source_open
    zone_high = source_open if bias == "Long" else source_high
    return {
        "bias": bias,
        "ob_type": ob_type,
        "source_index": source_index,
        "engulf_index": engulf_index,
        # OB zone stays anchored to the source candle, not the engulfing candle.
        "low": zone_low,
        "high": zone_high,
        "strict_body_engulf": bool(strict_body),
        "source_body_ratio": source_body_ratio,
        "engulf_body_ratio": engulf_body_ratio,
        "engulf_displacement_ratio": displacement_ratio,
    }


def find_ob_candidates(
    rates,
    scan_start=HTF_ORDER_BLOCK_SCAN_START,
    avg_range=None,
    point=0.0,
    strict_body=HTF_OB_USE_STRICT_BODY_ENGULF,
):
    if rates is None or len(rates) < HTF_ORDER_BLOCK_MIN_BARS:
        return []

    candidates = []

    for engulf_index in range(max(int(scan_start) + 1, 1), len(rates)):
        source_index = engulf_index - 1

        if is_bullish_engulfing(rates, source_index, engulf_index, strict_body=strict_body):
            passed, source_body_ratio, engulf_body_ratio, displacement_ratio = _passes_candidate_quality_filters(
                rates,
                source_index,
                engulf_index,
                avg_range,
                point,
            )
            if not passed:
                continue
            candidates.append(
                _build_ob_candidate(
                    rates,
                    source_index,
                    engulf_index,
                    "Long",
                    "Bullish",
                    strict_body,
                    source_body_ratio,
                    engulf_body_ratio,
                    displacement_ratio,
                )
            )
            continue

        if not is_bearish_engulfing(rates, source_index, engulf_index, strict_body=strict_body):
            continue

        passed, source_body_ratio, engulf_body_ratio, displacement_ratio = _passes_candidate_quality_filters(
            rates,
            source_index,
            engulf_index,
            avg_range,
            point,
        )
        if not passed:
            continue
        candidates.append(
            _build_ob_candidate(
                rates,
                source_index,
                engulf_index,
                "Short",
                "Bearish",
                strict_body,
                source_body_ratio,
                engulf_body_ratio,
                displacement_ratio,
            )
        )

    return candidates


def _score_valid_ob(validation, timeframe_name, avg_range):
    fvg_adjustment = HTF_ORDER_BLOCK_FVG_BONUS if validation["has_fvg"] else 0.0
    if not validation["has_fvg"] and _ob_fvg_mode() == "medium":
        fvg_adjustment = -abs(float(HTF_OB_FVG_PENALTY))
    return clamp(
        HTF_ORDER_BLOCK_QUALITY_BASE
        + HTF_ORDER_BLOCK_TIMEFRAME_BONUS[timeframe_name]
        + HTF_ORDER_BLOCK_BOS_BONUS
        + HTF_ORDER_BLOCK_DISPLACEMENT_BONUS[validation["displacement"]["strength"]]
        + clamp(validation["displacement"]["net_move"] / max(avg_range * 2.0, 1e-9)) * HTF_ORDER_BLOCK_QUALITY_SCALE
        + fvg_adjustment
        + (HTF_ORDER_BLOCK_SWEEP_BONUS if validation["liquidity_sweep"] else 0.0)
        + (HTF_ORDER_BLOCK_TREND_ALIGNMENT_BONUS if validation["trend_aligned"] else 0.0)
    )


def _candidate_has_supporting_fvg(rates, candidate, break_index, avg_range, point):
    start_index = int(candidate.get("engulf_index", candidate["source_index"] + 1))
    # Supporting FVG must form on the displacement leg after engulfing and before / at BOS break.
    return has_impulse_fvg(
        rates,
        candidate["bias"],
        avg_range,
        point,
        start_index,
        break_index,
    )


def _priority_rank(has_fvg, liquidity_sweep, fvg_mode):
    if has_fvg:
        return "OB + FVG"
    if liquidity_sweep:
        return "OB + liquidity sweep"
    if fvg_mode == "medium":
        return "OB only (no FVG penalty)"
    return "OB only"


def find_order_blocks(rates, timeframe_name, avg_range, point, zone_builder):
    if rates is None or len(rates) < HTF_ORDER_BLOCK_MIN_BARS:
        return []

    swings = build_swing_structure(
        rates,
        avg_range,
        left=HTF_SWING_STRENGTH,
        right=HTF_SWING_STRENGTH,
        min_range_ratio=HTF_SWING_MIN_RANGE_RATIO,
    )
    zones = []
    fvg_mode = _ob_fvg_mode()

    for candidate in find_ob_candidates(rates, avg_range=avg_range, point=point):
        trend = infer_trend_from_swings(swings["highs"], swings["lows"], candidate["source_index"])
        validation = is_valid_ob(rates, candidate, avg_range, point, swings=swings, trend=trend)
        if not validation["valid"]:
            continue

        validation["has_fvg"] = _candidate_has_supporting_fvg(
            rates,
            candidate,
            validation["break_index"],
            avg_range,
            point,
        )
        if fvg_mode == "strict" and not validation["has_fvg"]:
            continue

        validation["priority_rank"] = _priority_rank(
            validation["has_fvg"],
            validation["liquidity_sweep"],
            fvg_mode,
        )
        quality = _score_valid_ob(validation, timeframe_name, avg_range)

        zones.append(
            zone_builder(
                label=f"{timeframe_name} OB",
                timeframe=timeframe_name,
                zone_type="OB",
                bias=candidate["bias"],
                low=candidate["low"],
                high=candidate["high"],
                quality=quality,
                source_index=candidate["source_index"],
                engulf_index=candidate["engulf_index"],
                ob_type=candidate["ob_type"],
                strict_body_engulf=candidate["strict_body_engulf"],
                source_body_ratio=candidate["source_body_ratio"],
                engulf_body_ratio=candidate["engulf_body_ratio"],
                engulf_displacement_ratio=candidate["engulf_displacement_ratio"],
                fvg_mode=fvg_mode,
                bos_valid=validation["bos_valid"],
                displacement_strength=validation["displacement"]["strength"],
                has_fvg=validation["has_fvg"],
                liquidity_sweep=validation["liquidity_sweep"],
                trend=validation["trend"],
                trend_aligned=validation["trend_aligned"],
                broken_swing_level=float(validation["swing"]["price"]),
                break_index=validation["break_index"],
                priority_rank=validation["priority_rank"],
                external_structure=True,
                final_quality_score=quality,
            )
        )

    zones.sort(
        key=lambda zone: (
            zone["quality"],
            1 if zone.get("has_fvg") else 0,
            1 if zone.get("liquidity_sweep") else 0,
            1 if zone.get("trend_aligned") else 0,
            zone["source_index"],
        ),
        reverse=True,
    )
    return zones[:HTF_ORDER_BLOCK_MAX_ZONES]
