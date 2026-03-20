from ..config.htf import HTF_SWING_MIN_RANGE_RATIO, HTF_SWING_MIN_SEPARATION, HTF_SWING_STRENGTH


def find_swing_highs(rates, left=HTF_SWING_STRENGTH, right=HTF_SWING_STRENGTH):
    if rates is None or len(rates) < left + right + 1:
        return []

    highs = rates["high"]
    swings = []
    for index in range(left, len(rates) - right):
        price = float(highs[index])
        if all(price > float(value) for value in highs[index - left : index]) and all(
            price > float(value) for value in highs[index + 1 : index + 1 + right]
        ):
            swings.append({"index": index, "price": price, "left": left, "right": right})
    return swings


def find_swing_lows(rates, left=HTF_SWING_STRENGTH, right=HTF_SWING_STRENGTH):
    if rates is None or len(rates) < left + right + 1:
        return []

    lows = rates["low"]
    swings = []
    for index in range(left, len(rates) - right):
        price = float(lows[index])
        if all(price < float(value) for value in lows[index - left : index]) and all(
            price < float(value) for value in lows[index + 1 : index + 1 + right]
        ):
            swings.append({"index": index, "price": price, "left": left, "right": right})
    return swings


def _annotate_swing_significance(rates, swings, kind, avg_range, left, right, min_range_ratio):
    highs = rates["high"]
    lows = rates["low"]
    annotated = []

    for swing in swings:
        index = swing["index"]
        start = max(0, index - left)
        end = min(len(rates), index + right + 1)
        if kind == "high":
            span = float(highs[index] - lows[start:end].min())
        else:
            span = float(highs[start:end].max() - lows[index])
        annotated.append(
            {
                **swing,
                "span": span,
                "significant": span >= avg_range * min_range_ratio,
            }
        )

    return annotated


def build_swing_structure(
    rates,
    avg_range,
    left=HTF_SWING_STRENGTH,
    right=HTF_SWING_STRENGTH,
    min_range_ratio=HTF_SWING_MIN_RANGE_RATIO,
):
    swing_highs = find_swing_highs(rates, left=left, right=right)
    swing_lows = find_swing_lows(rates, left=left, right=right)
    return {
        "highs": _annotate_swing_significance(
            rates,
            swing_highs,
            "high",
            avg_range,
            left,
            right,
            min_range_ratio,
        ),
        "lows": _annotate_swing_significance(
            rates,
            swing_lows,
            "low",
            avg_range,
            left,
            right,
            min_range_ratio,
        ),
    }


def get_last_confirmed_swing_high_before(
    swings,
    index,
    min_separation=HTF_SWING_MIN_SEPARATION,
    require_significant=True,
):
    candidates = [
        swing
        for swing in swings
        if swing["index"] <= index - min_separation
        and (swing.get("significant", True) or not require_significant)
    ]
    return candidates[-1] if candidates else None


def get_last_confirmed_swing_low_before(
    swings,
    index,
    min_separation=HTF_SWING_MIN_SEPARATION,
    require_significant=True,
):
    candidates = [
        swing
        for swing in swings
        if swing["index"] <= index - min_separation
        and (swing.get("significant", True) or not require_significant)
    ]
    return candidates[-1] if candidates else None


def infer_trend_from_swings(swing_highs, swing_lows, index):
    recent_highs = [swing for swing in swing_highs if swing.get("significant", True) and swing["index"] <= index][-2:]
    recent_lows = [swing for swing in swing_lows if swing.get("significant", True) and swing["index"] <= index][-2:]

    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return "Range"
    if recent_highs[-1]["price"] > recent_highs[-2]["price"] and recent_lows[-1]["price"] > recent_lows[-2]["price"]:
        return "Bullish"
    if recent_highs[-1]["price"] < recent_highs[-2]["price"] and recent_lows[-1]["price"] < recent_lows[-2]["price"]:
        return "Bearish"
    return "Range"


def summarize_market_structure(
    rates,
    avg_range,
    index=None,
    left=HTF_SWING_STRENGTH,
    right=HTF_SWING_STRENGTH,
):
    if rates is None or len(rates) < left + right + 6:
        return {"trend": "Range", "clear": False, "highs": [], "lows": []}

    if index is None:
        index = len(rates) - 1

    swings = build_swing_structure(
        rates,
        avg_range,
        left=left,
        right=right,
    )
    recent_highs = [swing for swing in swings["highs"] if swing.get("significant", True) and swing["index"] <= index][-2:]
    recent_lows = [swing for swing in swings["lows"] if swing.get("significant", True) and swing["index"] <= index][-2:]
    trend = infer_trend_from_swings(swings["highs"], swings["lows"], index)
    clear = trend != "Range" and len(recent_highs) >= 2 and len(recent_lows) >= 2
    return {
        "trend": trend,
        "clear": clear,
        "highs": recent_highs,
        "lows": recent_lows,
    }
