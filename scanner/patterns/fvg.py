from ..config.htf import (
    HTF_FVG_DISPLACEMENT_BONUS,
    HTF_FVG_MAX_ZONES,
    HTF_FVG_MIN_BARS,
    HTF_FVG_LOOKBACK,
    HTF_FVG_QUALITY_BASE,
    HTF_FVG_QUALITY_DIVISOR,
    HTF_FVG_QUALITY_SCALE,
    HTF_FVG_TIMEFRAME_BONUS,
)
from ..utils import clamp
from .validators import is_valid_fvg


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
                    "bias": "Long",
                    "source_index": index,
                    "low": float(highs[index - lookback]),
                    "high": float(lows[index]),
                    "width": bullish_gap,
                }
            )
        if bias in (None, "Short") and bearish_gap > 0:
            candidates.append(
                {
                    "bias": "Short",
                    "source_index": index,
                    "low": float(highs[index]),
                    "high": float(lows[index - lookback]),
                    "width": bearish_gap,
                }
            )

    return candidates


def _score_valid_fvg(validation, timeframe_name, avg_range):
    return clamp(
        HTF_FVG_QUALITY_BASE
        + HTF_FVG_TIMEFRAME_BONUS[timeframe_name]
        + clamp(validation["width"] / max(avg_range * HTF_FVG_QUALITY_DIVISOR, 1e-9)) * HTF_FVG_QUALITY_SCALE
        + (HTF_FVG_DISPLACEMENT_BONUS if validation["formed_in_displacement"] else 0.0)
    )


def has_impulse_fvg(rates, bias, avg_range, point, start_index, end_index):
    candidates = find_fvg_candidates(
        rates,
        bias=bias,
        start_index=start_index,
        end_index=end_index,
    )
    return any(is_valid_fvg(candidate, rates, avg_range, point)["valid"] for candidate in candidates)


def find_fvgs(rates, timeframe_name, avg_range, point, zone_builder):
    zones = []
    for candidate in find_fvg_candidates(rates):
        validation = is_valid_fvg(candidate, rates, avg_range, point)
        if not validation["valid"]:
            continue

        zones.append(
            zone_builder(
                label=f"{timeframe_name} FVG",
                timeframe=timeframe_name,
                zone_type="FVG",
                bias=candidate["bias"],
                low=candidate["low"],
                high=candidate["high"],
                quality=_score_valid_fvg(validation, timeframe_name, avg_range),
                source_index=candidate["source_index"],
                formed_in_displacement=validation["formed_in_displacement"],
            )
        )

    zones.sort(key=lambda zone: zone["source_index"])
    return zones[-HTF_FVG_MAX_ZONES :]
