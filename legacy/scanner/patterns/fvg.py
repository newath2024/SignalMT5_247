from ..config.htf import (
    HTF_FVG_MAX_ZONES,
    HTF_FVG_MIN_BARS,
    HTF_FVG_LOOKBACK,
)
from .fvg_assessment import assess_fvg_candidate
from .swings import build_swing_structure


def find_fvg_candidates(rates, lookback=HTF_FVG_LOOKBACK, bias=None, start_index=None, end_index=None):
    if rates is None or len(rates) < HTF_FVG_MIN_BARS:
        return []

    highs = rates["high"]
    lows = rates["low"]
    start = max(lookback, start_index or lookback)
    end = min(len(rates) - 1, end_index if end_index is not None else len(rates) - 1)
    candidates = []

    for index in range(start, end + 1):
        bullish_gap = float(lows[index] - highs[index - lookback])
        bearish_gap = float(lows[index - lookback] - highs[index])

        if bias in (None, "Long") and bullish_gap > 0:
            candidates.append(
                {
                    "geometric_fvg": True,
                    "bias": "Long",
                    "start_index": index - lookback,
                    "middle_index": index - 1,
                    "source_index": index,
                    "low": float(highs[index - lookback]),
                    "high": float(lows[index]),
                    "width": bullish_gap,
                }
            )
        if bias in (None, "Short") and bearish_gap > 0:
            candidates.append(
                {
                    "geometric_fvg": True,
                    "bias": "Short",
                    "start_index": index - lookback,
                    "middle_index": index - 1,
                    "source_index": index,
                    "low": float(highs[index]),
                    "high": float(lows[index - lookback]),
                    "width": bearish_gap,
                }
            )

    return candidates


def has_impulse_fvg(rates, bias, avg_range, point, start_index, end_index):
    swings = build_swing_structure(rates, avg_range)
    candidates = find_fvg_candidates(
        rates,
        bias=bias,
        start_index=start_index,
        end_index=end_index,
    )
    for candidate in candidates:
        validation = assess_fvg_candidate(candidate, rates, "H1", avg_range, point, swings=swings)
        if validation["tradable"] and validation["formed_in_displacement"] and validation["follow_through_confirmed"]:
            return True
    return False


def find_fvgs(rates, timeframe_name, avg_range, point, zone_builder):
    swings = build_swing_structure(rates, avg_range)
    zones = []
    for candidate in find_fvg_candidates(rates):
        validation = assess_fvg_candidate(candidate, rates, timeframe_name, avg_range, point, swings=swings)
        if not validation["keep"]:
            continue

        zones.append(
            zone_builder(
                label=f"{timeframe_name} FVG",
                timeframe=timeframe_name,
                zone_type="FVG",
                bias=candidate["bias"],
                low=candidate["low"],
                high=candidate["high"],
                quality=validation["quality"],
                source_index=candidate["source_index"],
                formed_in_displacement=validation["formed_in_displacement"],
                geometric_fvg=True,
                valid_fvg=validation["valid"],
                tradable=validation["tradable"],
                displacement_strength=validation["displacement_strength"],
                after_bos=validation["after_bos"],
                near_liquidity_sweep=validation["near_liquidity_sweep"],
                trend=validation["trend"],
                trend_aligned=validation["trend_aligned"],
                location_in_range=validation["location_in_range"],
                fvg_class=validation["fvg_class"],
                mitigation_status=validation["mitigation_status"],
                mitigation_ratio=validation["mitigation_ratio"],
                follow_through_strength=validation["follow_through_strength"],
                follow_through_confirmed=validation["follow_through_confirmed"],
                follow_through_fill_ratio=validation["follow_through_fill_ratio"],
                quality_components=validation["quality_components"],
                quality_penalties=validation["quality_penalties"],
                context_signals=validation["context_signals"],
                rejection_reason=validation["rejection_reason"],
                bos_index=validation["bos_index"],
                sweep_index=validation["sweep_index"],
                fvg_debug=validation["debug"],
            )
        )

    zones.sort(
        key=lambda zone: (
            zone["quality"],
            1 if zone.get("tradable") else 0,
            zone["source_index"],
        ),
        reverse=True,
    )
    return zones[:HTF_FVG_MAX_ZONES]
