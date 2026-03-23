import datetime as dt

from ..config import ASIA_SESSION_UTC, HISTORY_BARS, LONDON_SESSION_UTC, TIMEFRAME_MAP
from ..deps import mt5
from .mt5_client import ensure_symbol_ready, get_candles, get_current_price, get_live_candle, get_symbol_tick


def infer_server_utc_offset_hours(tick):
    if tick is None or not tick.time:
        return 0
    utc_now = dt.datetime.now(dt.timezone.utc).timestamp()
    return int(round((float(tick.time) - utc_now) / 3600.0))


def broker_datetime_from_timestamp(timestamp):
    return dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc)


def build_session_window(broker_now, offset_hours, start_utc_hour, end_utc_hour):
    utc_reference = broker_now - dt.timedelta(hours=offset_hours)
    utc_date = utc_reference.date()
    session_start = dt.datetime.combine(
        utc_date,
        dt.time(start_utc_hour, 0),
        tzinfo=dt.timezone.utc,
    ) + dt.timedelta(hours=offset_hours)
    session_end = dt.datetime.combine(
        utc_date,
        dt.time(end_utc_hour, 0),
        tzinfo=dt.timezone.utc,
    ) + dt.timedelta(hours=offset_hours)
    return session_start, session_end


def find_completed_session_extrema(rates, broker_now, offset_hours, start_utc_hour, end_utc_hour):
    if rates is None or len(rates) == 0:
        return None

    session_start, session_end = build_session_window(
        broker_now,
        offset_hours,
        start_utc_hour,
        end_utc_hour,
    )
    if broker_now < session_end:
        return None

    session_bars = [
        candle
        for candle in rates
        if session_start <= broker_datetime_from_timestamp(candle["time"]) < session_end
    ]
    if not session_bars:
        return None

    return {
        "high": max(float(candle["high"]) for candle in session_bars),
        "low": min(float(candle["low"]) for candle in session_bars),
        "start": session_start,
        "end": session_end,
    }


def build_reference_levels(rates_by_name, broker_now, offset_hours):
    references = {}
    previous_day = rates_by_name["D1"][-1]
    previous_week = rates_by_name["W1"][-1]
    references["PDH"] = float(previous_day["high"])
    references["PDL"] = float(previous_day["low"])
    references["PWH"] = float(previous_week["high"])
    references["PWL"] = float(previous_week["low"])

    asia_session = find_completed_session_extrema(
        rates_by_name["M5"],
        broker_now,
        offset_hours,
        ASIA_SESSION_UTC[0],
        ASIA_SESSION_UTC[1],
    )
    if asia_session is not None:
        references["ASH"] = asia_session["high"]
        references["ASL"] = asia_session["low"]

    london_session = find_completed_session_extrema(
        rates_by_name["M5"],
        broker_now,
        offset_hours,
        LONDON_SESSION_UTC[0],
        LONDON_SESSION_UTC[1],
    )
    if london_session is not None:
        references["LOH"] = london_session["high"]
        references["LOL"] = london_session["low"]

    return references


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
    reference_levels = build_reference_levels(
        rates_by_name,
        broker_now,
        server_utc_offset_hours,
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
        "reference_levels": reference_levels,
    }
