from __future__ import annotations

from infra.config.loader import AppConfig


def build_startup_diagnostics(config: AppConfig) -> dict[str, str]:
    """Build the startup diagnostics summary emitted during bootstrap."""
    return {
        "app_name": config.app.name,
        "strategy": f"{config.app.strategy_name} v{config.app.strategy_version}",
        "htf_inputs": ", ".join(config.scanner.htf_timeframes),
        "canonical_htf": ", ".join(config.scanner.canonical_htf_timeframes) or "-",
        "legacy_htf_inputs": ", ".join(config.scanner.legacy_htf_timeframes) or "-",
        "ltf_list": ", ".join(config.scanner.ltf_timeframes),
        "strict_ifvg": "enabled" if config.scanner.strict_ifvg else "disabled",
        "symbols_count": str(len(config.scanner.symbols)),
        "scan_interval": f"{config.scanner.loop_interval_sec}s",
    }
