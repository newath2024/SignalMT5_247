"""Bridges for legacy HTF/LTF detection primitives."""

from __future__ import annotations

from legacy.scanner.htf import build_htf_zones, evaluate_htf_zone, select_htf_contexts
from legacy.scanner.ltf.execution import build_signal
from legacy.scanner.ltf.sweep import detect_ltf_watch_trigger
from legacy.scanner.ltf.trigger import detect_mss_confirmation
from legacy.scanner.config.ltf import (
    SIGNAL_AMBIGUITY_DELTA,
    TIMEFRAME_PRIORITY,
    WATCH_EXPIRY_BARS,
    WATCH_INVALIDATION_BUFFER_POINTS,
)


def get_ltf_config() -> dict:
    return {
        "signal_ambiguity_delta": SIGNAL_AMBIGUITY_DELTA,
        "timeframe_priority": TIMEFRAME_PRIORITY,
        "watch_expiry_bars": WATCH_EXPIRY_BARS,
        "watch_invalidation_buffer_points": WATCH_INVALIDATION_BUFFER_POINTS,
    }


def build_watch_trigger(rates, bias, current_price, point, timeframe_name, reference_levels, context):
    return detect_ltf_watch_trigger(
        rates,
        bias,
        current_price,
        point,
        timeframe_name,
        reference_levels,
        context,
    )


def build_signal_from_watch(snapshot, context, trigger, timeframe, all_htf_zones):
    return build_signal(snapshot, context, trigger, timeframe, all_htf_zones)


__all__ = [
    "build_htf_zones",
    "build_signal_from_watch",
    "build_watch_trigger",
    "detect_mss_confirmation",
    "evaluate_htf_zone",
    "get_ltf_config",
    "select_htf_contexts",
]
