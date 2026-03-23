from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "build_swing_structure": (".swings", "build_swing_structure"),
    "displacement_strength": (".validators", "displacement_strength"),
    "find_first_touch_after_creation": (".ifvg", "find_first_touch_after_creation"),
    "find_fvg_candidates": (".fvg", "find_fvg_candidates"),
    "find_fvgs": (".fvg", "find_fvgs"),
    "find_ifvg_candidates": (".ifvg", "find_ifvg_candidates"),
    "find_ifvg_zone": (".ifvg", "find_ifvg_zone"),
    "find_ob_candidates": (".ob", "find_ob_candidates"),
    "find_order_blocks": (".ob", "find_order_blocks"),
    "find_swing_highs": (".swings", "find_swing_highs"),
    "find_swing_lows": (".swings", "find_swing_lows"),
    "get_last_confirmed_swing_high_before": (".swings", "get_last_confirmed_swing_high_before"),
    "get_last_confirmed_swing_low_before": (".swings", "get_last_confirmed_swing_low_before"),
    "has_clean_post_ob_move": (".validators", "has_clean_post_ob_move"),
    "has_overlap_after_zone": (".validators", "has_overlap_after_zone"),
    "infer_trend_from_swings": (".swings", "infer_trend_from_swings"),
    "is_bearish_engulfing": (".ob", "is_bearish_engulfing"),
    "is_bullish_engulfing": (".ob", "is_bullish_engulfing"),
    "is_clean_ifvg_inversion": (".ifvg", "is_clean_ifvg_inversion"),
    "is_valid_bos": (".validators", "is_valid_bos"),
    "is_valid_fvg": (".validators", "is_valid_fvg"),
    "is_valid_ifvg": (".validators", "is_valid_ifvg"),
    "is_valid_ob": (".validators", "is_valid_ob"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
