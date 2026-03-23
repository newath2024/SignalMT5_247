from ..config.htf import (
    HTF_DISPLACEMENT_MAX_OPPOSITE_BARS,
    HTF_DISPLACEMENT_MAX_WEAK_BODY_BARS,
    HTF_DISPLACEMENT_MIN_BARS,
    HTF_DISPLACEMENT_MIN_BODY_MEDIUM,
    HTF_DISPLACEMENT_MIN_BODY_STRONG,
    HTF_DISPLACEMENT_MIN_DIRECTIONAL_RATIO,
    HTF_DISPLACEMENT_MIN_EFFICIENCY_MEDIUM,
    HTF_DISPLACEMENT_MIN_EFFICIENCY_STRONG,
    HTF_DISPLACEMENT_MIN_MOVE_MEDIUM,
    HTF_DISPLACEMENT_MIN_MOVE_STRONG,
)
from ..utils import body_strength


def displacement_strength(rates, start_index, end_index, bias, avg_range, point):
    impulse = rates[start_index : end_index + 1]
    if len(impulse) < HTF_DISPLACEMENT_MIN_BARS:
        return None

    ranges = [max(float(candle["high"] - candle["low"]), point) for candle in impulse]
    body_scores = [body_strength(candle, point) for candle in impulse]
    avg_body = sum(body_scores) / len(body_scores)

    if bias == "Long":
        directional_bars = sum(1 for candle in impulse if float(candle["close"]) > float(candle["open"]))
        net_move = float(impulse["high"].max()) - float(rates["high"][start_index - 1])
    else:
        directional_bars = sum(1 for candle in impulse if float(candle["close"]) < float(candle["open"]))
        net_move = float(rates["low"][start_index - 1]) - float(impulse["low"].min())

    opposite_bars = len(impulse) - directional_bars
    weak_body_bars = sum(1 for score in body_scores if score < HTF_DISPLACEMENT_MIN_BODY_MEDIUM)
    directional_ratio = directional_bars / len(impulse)
    efficiency = net_move / max(sum(ranges), point)

    if (
        net_move >= avg_range * HTF_DISPLACEMENT_MIN_MOVE_STRONG
        and avg_body >= HTF_DISPLACEMENT_MIN_BODY_STRONG
        and efficiency >= HTF_DISPLACEMENT_MIN_EFFICIENCY_STRONG
        and directional_ratio >= HTF_DISPLACEMENT_MIN_DIRECTIONAL_RATIO
    ):
        strength = "strong"
    elif (
        net_move >= avg_range * HTF_DISPLACEMENT_MIN_MOVE_MEDIUM
        and avg_body >= HTF_DISPLACEMENT_MIN_BODY_MEDIUM
        and efficiency >= HTF_DISPLACEMENT_MIN_EFFICIENCY_MEDIUM
        and directional_ratio >= HTF_DISPLACEMENT_MIN_DIRECTIONAL_RATIO
    ):
        strength = "medium"
    else:
        strength = "weak"

    return {
        "valid": (
            strength != "weak"
            and opposite_bars <= HTF_DISPLACEMENT_MAX_OPPOSITE_BARS
            and weak_body_bars <= HTF_DISPLACEMENT_MAX_WEAK_BODY_BARS
        ),
        "strength": strength,
        "avg_body": avg_body,
        "directional_ratio": directional_ratio,
        "efficiency": efficiency,
        "net_move": net_move,
        "opposite_bars": opposite_bars,
        "weak_body_bars": weak_body_bars,
    }
