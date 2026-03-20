from ..config.htf import (
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
from ..utils import clamp
from .fvg import has_impulse_fvg
from .swings import build_swing_structure, infer_trend_from_swings
from .validators import is_valid_ob


def find_ob_candidates(rates, scan_start=HTF_ORDER_BLOCK_SCAN_START):
    if rates is None or len(rates) < HTF_ORDER_BLOCK_MIN_BARS:
        return []

    opens = rates["open"]
    closes = rates["close"]
    highs = rates["high"]
    lows = rates["low"]
    candidates = []

    for index in range(scan_start, len(rates)):
        if float(closes[index]) < float(opens[index]):
            candidates.append(
                {
                    "bias": "Long",
                    "ob_type": "Bullish",
                    "source_index": index,
                    "low": float(lows[index]),
                    "high": float(max(opens[index], closes[index])),
                }
            )
        elif float(closes[index]) > float(opens[index]):
            candidates.append(
                {
                    "bias": "Short",
                    "ob_type": "Bearish",
                    "source_index": index,
                    "low": float(min(opens[index], closes[index])),
                    "high": float(highs[index]),
                }
            )

    return candidates


def _score_valid_ob(validation, timeframe_name, avg_range):
    return clamp(
        HTF_ORDER_BLOCK_QUALITY_BASE
        + HTF_ORDER_BLOCK_TIMEFRAME_BONUS[timeframe_name]
        + HTF_ORDER_BLOCK_BOS_BONUS
        + HTF_ORDER_BLOCK_DISPLACEMENT_BONUS[validation["displacement"]["strength"]]
        + clamp(validation["displacement"]["net_move"] / max(avg_range * 2.0, 1e-9)) * HTF_ORDER_BLOCK_QUALITY_SCALE
        + (HTF_ORDER_BLOCK_FVG_BONUS if validation["has_fvg"] else 0.0)
        + (HTF_ORDER_BLOCK_SWEEP_BONUS if validation["liquidity_sweep"] else 0.0)
        + (HTF_ORDER_BLOCK_TREND_ALIGNMENT_BONUS if validation["trend_aligned"] else 0.0)
    )


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

    for candidate in find_ob_candidates(rates):
        trend = infer_trend_from_swings(swings["highs"], swings["lows"], candidate["source_index"])
        validation = is_valid_ob(rates, candidate, avg_range, point, swings=swings, trend=trend)
        if not validation["valid"]:
            continue

        validation["has_fvg"] = has_impulse_fvg(
            rates,
            candidate["bias"],
            avg_range,
            point,
            candidate["source_index"] + 1,
            validation["break_index"],
        )
        validation["priority_rank"] = (
            "OB + FVG"
            if validation["has_fvg"]
            else ("OB + liquidity sweep" if validation["liquidity_sweep"] else "OB only")
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
                ob_type=candidate["ob_type"],
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
