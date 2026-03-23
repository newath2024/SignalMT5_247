"""Bridges for runtime knobs that still live in legacy scanner globals."""

from __future__ import annotations

import legacy.scanner.config.htf as htf_runtime_config
import legacy.scanner.patterns.ob as ob_runtime

VALID_OB_FVG_MODES = {"strict", "medium"}


def normalize_ob_fvg_mode(mode: str | None) -> str:
    value = str(mode or "medium").strip().lower()
    if value not in VALID_OB_FVG_MODES:
        raise ValueError("OB FVG mode must be 'strict' or 'medium'.")
    return value


def set_ob_fvg_mode(mode: str) -> str:
    normalized = normalize_ob_fvg_mode(mode)
    htf_runtime_config.HTF_OB_FVG_MODE = normalized
    ob_runtime.HTF_OB_FVG_MODE = normalized
    return normalized


def get_ob_fvg_mode() -> str:
    return normalize_ob_fvg_mode(getattr(ob_runtime, "HTF_OB_FVG_MODE", "medium"))


__all__ = ["VALID_OB_FVG_MODES", "get_ob_fvg_mode", "normalize_ob_fvg_mode", "set_ob_fvg_mode"]
