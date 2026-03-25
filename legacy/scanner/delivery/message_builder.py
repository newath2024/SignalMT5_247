"""Compatibility shim for legacy signal captions.

Canonical implementation lives in ``domain.alerts``.
Safe to remove after import migration.
"""

from domain.alerts import build_signal_caption

__all__ = ["build_signal_caption"]
