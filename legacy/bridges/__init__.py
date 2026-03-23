"""Explicit bridge modules between the new architecture and the legacy scanner."""

from .detection import (
    build_signal_from_watch,
    build_watch_trigger,
    evaluate_htf_zone,
    get_ltf_config,
    select_htf_contexts,
)
from .market_data import build_symbol_snapshot
from .notifications import build_signal_caption, build_signal_charts
from .runtime_config import get_ob_fvg_mode, set_ob_fvg_mode

__all__ = [
    "build_signal_caption",
    "build_signal_charts",
    "build_signal_from_watch",
    "build_symbol_snapshot",
    "build_watch_trigger",
    "evaluate_htf_zone",
    "get_ltf_config",
    "get_ob_fvg_mode",
    "select_htf_contexts",
    "set_ob_fvg_mode",
]
