"""Compatibility shim for LTF confirmation detection.

Canonical implementation lives in ``domain.confirmation``.
Safe to remove after import migration.
"""

from domain.confirmation import (
    SIGNAL_AMBIGUITY_DELTA,
    WATCH_EXPIRY_BARS,
    WATCH_INVALIDATION_BUFFER_POINTS,
    build_watch_key,
    build_watch_setup,
    detect_confirmed_signal,
    detect_watch_candidates,
    watch_has_expired,
    watch_is_invalidated,
)

__all__ = [
    "SIGNAL_AMBIGUITY_DELTA",
    "WATCH_EXPIRY_BARS",
    "WATCH_INVALIDATION_BUFFER_POINTS",
    "build_watch_key",
    "build_watch_setup",
    "detect_confirmed_signal",
    "detect_watch_candidates",
    "watch_has_expired",
    "watch_is_invalidated",
]
