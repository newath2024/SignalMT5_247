"""Canonical application startup path.

This module owns the runtime startup flow:
1. load + validate config
2. build runtime via composition root
3. create lifecycle manager
4. create UI-facing controller facade
5. start lifecycle-managed services
"""

from __future__ import annotations

from infra.config import load_app_config

from .composition import build_app_runtime
from .controller import AppController
from .lifecycle import AppLifecycle


def build_application_controller() -> AppController:
    """Build the canonical application runtime and return the UI facade."""
    config = load_app_config()
    runtime = build_app_runtime(config)
    lifecycle = AppLifecycle(config=config, runtime=runtime)
    lifecycle.startup()
    return AppController(lifecycle)
