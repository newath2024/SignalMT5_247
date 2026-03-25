"""Canonical domain-level alert semantics and payload helpers.

Telegram transport formatting remains in ``infra.telegram``.
"""

from .messages import build_signal_caption, build_watch_armed_message

__all__ = ["build_signal_caption", "build_watch_armed_message"]
