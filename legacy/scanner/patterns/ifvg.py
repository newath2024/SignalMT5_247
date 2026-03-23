from ..config.ltf import (
    LTF_IFVG_INTERNAL_BASE_QUALITY,
    LTF_IFVG_INTERNAL_ENTRY_WEIGHT,
    LTF_IFVG_POST_BREAK_BARS,
    LTF_IFVG_SEARCH_BACK,
    LTF_IFVG_STRICT_BASE_QUALITY,
    LTF_IFVG_STRICT_ENTRY_WEIGHT,
    LTF_IFVG_WIDTH_QUALITY_SCALE,
)
from ..utils import clamp
from .fvg import find_fvg_candidates
from .validators import find_first_touch_after_creation, is_clean_ifvg_inversion, is_valid_ifvg


def find_ifvg_candidates(rates, bias, sweep_index, mss_index):
    strict_start = max(2, sweep_index - LTF_IFVG_SEARCH_BACK)
    strict_bias = "Short" if bias == "Long" else "Long"
    internal_bias = bias
    candidates = []

    def enrich_candidate(candidate, mode):
        # The middle candle of the 3-candle imbalance is the displacement candle
        # that actually creates the gap. We use its extreme for execution stops.
        origin_candle_index = candidate["source_index"] - 1
        return {
            **candidate,
            "mode": mode,
            "origin_candle_index": origin_candle_index,
            "origin_candle_high": float(rates["high"][origin_candle_index]),
            "origin_candle_low": float(rates["low"][origin_candle_index]),
        }

    for candidate in find_fvg_candidates(
        rates,
        bias=strict_bias,
        start_index=strict_start,
        end_index=mss_index,
    ):
        candidates.append(enrich_candidate(candidate, "strict"))

    for candidate in find_fvg_candidates(
        rates,
        bias=internal_bias,
        start_index=max(mss_index + 2, 2),
        end_index=len(rates) - 1,
    ):
        candidates.append(enrich_candidate(candidate, "internal"))

    return candidates


def _score_valid_ifvg(validation, avg_range, point):
    base = (
        LTF_IFVG_STRICT_BASE_QUALITY
        if validation["mode"] == "strict"
        else LTF_IFVG_INTERNAL_BASE_QUALITY
    )
    entry_weight = (
        LTF_IFVG_STRICT_ENTRY_WEIGHT
        if validation["mode"] == "strict"
        else LTF_IFVG_INTERNAL_ENTRY_WEIGHT
    )
    quality = (
        base
        + clamp(validation["width"] / max(avg_range, point)) * LTF_IFVG_WIDTH_QUALITY_SCALE
        + validation["entry_quality"] * entry_weight
    )
    return {
        "low": validation["low"],
        "high": validation["high"],
        "mode": validation["mode"],
        "quality": clamp(quality),
        "entry_quality": validation["entry_quality"],
        "source_index": validation["source_index"],
        "origin_candle_index": validation["origin_candle_index"],
        "origin_candle_high": validation["origin_candle_high"],
        "origin_candle_low": validation["origin_candle_low"],
        "entry_edge": validation["entry_edge"],
        "touch_index": validation["touch_index"],
        "post_break_confirmed": validation["post_break_confirmed"],
    }


def find_ifvg_zone(rates, bias, sweep_index, mss_index, current_price, avg_range, point):
    strict_matches = []
    internal_matches = []

    for candidate in find_ifvg_candidates(rates, bias, sweep_index, mss_index):
        validation = is_valid_ifvg(
            candidate,
            rates,
            bias,
            mss_index,
            current_price,
            avg_range,
            point,
        )
        if not validation["valid"]:
            continue

        scored = _score_valid_ifvg(validation, avg_range, point)
        if scored["mode"] == "strict":
            strict_matches.append(scored)
        else:
            internal_matches.append(scored)

    candidates = strict_matches or internal_matches
    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            1 if item["mode"] == "strict" else 0,
            item["entry_quality"],
            item["quality"],
            item["source_index"],
        ),
        reverse=True,
    )
    return candidates[0]
