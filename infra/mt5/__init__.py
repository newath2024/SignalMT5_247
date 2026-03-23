from .runtime import (
    MT5RuntimeReport,
    MT5SessionReport,
    MT5RuntimeSettings,
    apply_mt5_window_mode,
    check_mt5_session,
    connect_mt5_with_retry,
    launch_mt5_terminal,
    load_mt5_runtime_settings,
    wait_for_mt5_terminal,
)


def __getattr__(name: str):
    if name == "MT5DataGateway":
        from .gateway import MT5DataGateway

        return MT5DataGateway
    raise AttributeError(name)

__all__ = [
    "MT5DataGateway",
    "MT5RuntimeReport",
    "MT5SessionReport",
    "MT5RuntimeSettings",
    "apply_mt5_window_mode",
    "check_mt5_session",
    "connect_mt5_with_retry",
    "launch_mt5_terminal",
    "load_mt5_runtime_settings",
    "wait_for_mt5_terminal",
]
