"""Application lifecycle manager.

Canonical implementation for runtime startup, shutdown, and diagnostics.
"""

from __future__ import annotations

from dataclasses import replace

from infra.config import AppConfig, build_startup_diagnostics, save_user_config_patch
from legacy.bridges.runtime_config import get_ob_fvg_mode, normalize_ob_fvg_mode, set_ob_fvg_mode

from .composition import AppRuntime


class AppLifecycle:
    def __init__(self, config: AppConfig, runtime: AppRuntime):
        self.config = config
        self.runtime: AppRuntime = runtime
        self._started = False

    def startup(self) -> None:
        """Start long-lived lifecycle-managed services once."""
        if self._started:
            return
        self.runtime.scanner_service.start()
        self.runtime.telegram_bot.start()
        diagnostics = build_startup_diagnostics(self.config)
        self.runtime.logger.info(
            f"{self.config.app.name} v{self.config.app.version} started",
            phase="system",
            reason=f"strategy v{self.config.app.strategy_version}",
        )
        self.runtime.logger.info(
            "Startup diagnostics",
            phase="system",
            reason=" | ".join(f"{key}={value}" for key, value in diagnostics.items()),
        )
        self._started = True

    @staticmethod
    def normalize_ob_fvg_mode(mode: str | None) -> str:
        return normalize_ob_fvg_mode(mode)

    def set_ob_fvg_mode(self, mode: str, persist: bool = True) -> tuple[bool, str]:
        try:
            normalized = set_ob_fvg_mode(mode)
        except ValueError as exc:
            return False, str(exc)
        self.config = replace(self.config, scanner=replace(self.config.scanner, ob_fvg_mode=normalized))
        self.runtime.config = self.config
        if persist:
            save_user_config_patch({"scanner": {"ob_fvg_mode": normalized}})
        self.runtime.logger.info(
            "HTF OB FVG mode updated",
            phase="system",
            reason=f"mode={normalized}",
        )
        return True, f"HTF OB FVG mode set to {normalized}."

    def current_ob_fvg_mode(self) -> str:
        return get_ob_fvg_mode()

    def shutdown(self) -> None:
        if not self._started:
            return
        self.runtime.telegram_bot.stop()
        self.runtime.scanner_service.stop()
        self.runtime.engine.stop()
        self._started = False
