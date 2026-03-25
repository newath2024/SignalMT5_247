"""Compatibility shim for HTF context detection.

Canonical implementation lives in ``domain.context``.
Safe to remove after import migration.
"""

from domain.context import detect_htf_context, refresh_htf_context

__all__ = ["detect_htf_context", "refresh_htf_context"]
