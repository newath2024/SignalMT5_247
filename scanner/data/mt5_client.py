from ..deps import mt5
from ..utils import log, notify_once
from core.mt5_runtime import connect_mt5_with_retry, load_mt5_runtime_settings


_MT5_SETTINGS = load_mt5_runtime_settings()


def connect_mt5():
    report = connect_mt5_with_retry(mt5, settings=_MT5_SETTINGS)
    if not report.ready:
        raise RuntimeError(report.message)
    log(f"Connected to MT5: {report.terminal_name or 'Unknown terminal'}")


def ensure_symbol_ready(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        notify_once(
            f"missing:{symbol}",
            f"Skip {symbol}: symbol was not found in this MT5 terminal.",
        )
        return False

    if not info.visible and not mt5.symbol_select(symbol, True):
        notify_once(
            f"not_visible:{symbol}",
            f"Skip {symbol}: symbol exists but could not be enabled in Market Watch.",
        )
        return False

    if info.visible is False:
        notify_once(
            f"selected:{symbol}",
            f"Enabled hidden symbol in Market Watch: {symbol}",
        )

    return True


def get_candles(symbol, timeframe, count, include_current=False):
    requested = count + (0 if include_current else 1)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, requested)
    if rates is None:
        error_code, error_message = mt5.last_error()
        log(
            f"Failed to load candles for {symbol} on timeframe {timeframe}: "
            f"[{error_code}] {error_message}"
        )
        return None

    if len(rates) == 0:
        return None

    if not include_current and len(rates) > 1:
        rates = rates[:-1]

    return rates if len(rates) else None


def get_live_candle(symbol, timeframe):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
    if rates is None:
        error_code, error_message = mt5.last_error()
        log(
            f"Failed to load live candle for {symbol} on timeframe {timeframe}: "
            f"[{error_code}] {error_message}"
        )
        return None
    if len(rates) == 0:
        return None
    return rates[-1]


def get_current_price(symbol, fallback_price):
    tick = mt5.symbol_info_tick(symbol)
    if tick and tick.bid and tick.ask:
        return float((tick.bid + tick.ask) / 2.0)
    return float(fallback_price)


def get_symbol_tick(symbol):
    tick = mt5.symbol_info_tick(symbol)
    return tick if tick and tick.time else None
