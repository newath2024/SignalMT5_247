"""Desktop UI exports.

Keep business logic in ``domain`` / ``services`` and use ``ui`` for
presentation-only behavior.
"""

from .main_window import launch_desktop

__all__ = ["launch_desktop"]
