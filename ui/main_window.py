"""Compatibility shim for the desktop main window.

Canonical implementation lives in ``ui.views.main_window``.
Safe to remove after all imports migrate to the ``ui.views`` namespace.
"""

from .views.main_window import MainWindow, launch_desktop

__all__ = ["MainWindow", "launch_desktop"]
