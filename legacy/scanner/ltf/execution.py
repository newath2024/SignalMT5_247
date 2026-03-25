from ..config.ltf import (
    LTF_ACTIONABLE_MIN_POINTS,
    LTF_ACTIONABLE_RISK_RATIO,
    LTF_ACTIONABLE_ZONE_HEIGHT_RATIO,
    LTF_MIN_RISK_POINTS,
    LTF_NO_CHASE_MIN_POINTS,
    LTF_NO_CHASE_MIN_SCORE,
    LTF_NO_CHASE_RISK_RATIO,
    WATCH_EXPIRY_BARS,
)
from ..signals.builder import build_signal as build_trade_signal
from ..utils import clamp, zone_distance
from .sweep import detect_ltf_watch_trigger


def compute_execution_plan(snapshot, trigger, trigger_timeframe):
    point = snapshot["point"]
    bias = trigger["bias"]
    current_price = snapshot["current_price"]
    ifvg = trigger["ifvg"]
    entry_zone_low = ifvg["low"]
    entry_zone_high = ifvg["high"]
    entry_price = ifvg["entry_edge"]
    stop_loss = ifvg["origin_candle_low"] if bias == "Long" else ifvg["origin_candle_high"]

    risk = abs(entry_price - stop_loss)
    if risk <= point * LTF_MIN_RISK_POINTS:
        return None

    zone_height = max(entry_zone_high - entry_zone_low, point * 4)
    entry_distance = zone_distance(current_price, entry_zone_low, entry_zone_high)
    moved_away = (
        max(0.0, current_price - entry_zone_high)
        if bias == "Long"
        else max(0.0, entry_zone_low - current_price)
    )
    actionable_limit = max(
        zone_height * LTF_ACTIONABLE_ZONE_HEIGHT_RATIO,
        risk * LTF_ACTIONABLE_RISK_RATIO,
        point * LTF_ACTIONABLE_MIN_POINTS,
    )
    if moved_away > actionable_limit:
        return None

    no_chase = clamp(
        1.0 - entry_distance / max(risk * LTF_NO_CHASE_RISK_RATIO, point * LTF_NO_CHASE_MIN_POINTS)
    )
    if no_chase < LTF_NO_CHASE_MIN_SCORE:
        return None

    actionability = clamp(1.0 - moved_away / actionable_limit)
    return {
        "entry_zone_low": entry_zone_low,
        "entry_zone_high": entry_zone_high,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk": risk,
        "no_chase": no_chase,
        "actionability": actionability,
    }


def detect_ltf_trigger(rates, bias, current_price, point, timeframe_name):
    from .trigger import detect_mss_confirmation

    watch_trigger, _ = detect_ltf_watch_trigger(
        rates,
        bias,
        current_price,
        point,
        timeframe_name,
        {"trend_alignment": "aligned", "structure_trend": "Range"},
    )
    if watch_trigger is None:
        return None

    watch_stub = {
        "bias": bias,
        "timeframe": timeframe_name,
        "watch_index": watch_trigger["watch_index"],
        "expiry_bar_index": watch_trigger["watch_index"] + WATCH_EXPIRY_BARS[timeframe_name],
        "structure_level": watch_trigger["structure_level"],
        "avg_range": watch_trigger["avg_range"],
        "ifvg": watch_trigger["ifvg"],
    }
    mss = detect_mss_confirmation(rates, bias, watch_stub, point)
    if mss is None:
        return None

    return {
        **watch_trigger,
        **mss,
    }


def build_signal(snapshot, context, trigger, trigger_timeframe, all_htf_zones):
    execution = compute_execution_plan(snapshot, trigger, trigger_timeframe)
    if execution is None:
        return None

    trigger = {**trigger, "execution": execution}
    return build_trade_signal(snapshot, context, trigger, trigger_timeframe, all_htf_zones)
