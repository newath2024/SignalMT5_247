import datetime as dt

from ..config import HISTORY_BARS, TIMEFRAME_MAP
from ..deps import mt5
from .mt5_client import ensure_symbol_ready, get_candles, get_current_price, get_live_candle, get_symbol_tick


def infer_server_utc_offset_hours(tick):
    if tick is None or not tick.time:
        return 0
    utc_now = dt.datetime.now(dt.timezone.utc).timestamp()
    return int(round((float(tick.time) - utc_now) / 3600.0))


def broker_datetime_from_timestamp(timestamp):
    return dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc)


def build_symbol_snapshot(symbol):
    if not ensure_symbol_ready(symbol):
        return None

    info = mt5.symbol_info(symbol)
    if info is None:
        return None

    rates_by_name = {}
    for name, timeframe in TIMEFRAME_MAP.items():
        rates = get_candles(symbol, timeframe, HISTORY_BARS[name], include_current=False)
        if rates is None:
            return None
        rates_by_name[name] = rates

    live_candles = {}
    for name in ("H1",):
        timeframe = TIMEFRAME_MAP[name]
        live_candle = get_live_candle(symbol, timeframe)
        if live_candle is not None:
            live_candles[name] = live_candle

    tick = get_symbol_tick(symbol)
    current_price = get_current_price(symbol, rates_by_name["M5"][-1]["close"])
    point = float(info.point) if info.point else 0.00001
    server_utc_offset_hours = infer_server_utc_offset_hours(tick)
    broker_now = (
        broker_datetime_from_timestamp(tick.time)
        if tick is not None
        else broker_datetime_from_timestamp(rates_by_name["M5"][-1]["time"])
    )
    return {
        "symbol": symbol,
        "info": info,
        "digits": int(info.digits),
        "point": point,
        "current_price": current_price,
        "rates": rates_by_name,
        "live_candles": live_candles,
        "broker_now": broker_now,
        "server_utc_offset_hours": server_utc_offset_hours,
    }
