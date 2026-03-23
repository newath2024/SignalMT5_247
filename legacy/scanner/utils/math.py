def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def zone_mid(zone):
    return (zone["low"] + zone["high"]) / 2.0


def zone_width(zone):
    return max(zone["high"] - zone["low"], 0.0)


def zone_distance(price, low, high):
    if price < low:
        return low - price
    if price > high:
        return price - high
    return 0.0


def average_range(rates, period=14):
    if rates is None or len(rates) == 0:
        return 0.0
    window = rates[-min(period, len(rates)) :]
    return float((window["high"] - window["low"]).mean())


def body_strength(candle, point):
    candle_range = max(float(candle["high"] - candle["low"]), point)
    body = abs(float(candle["close"] - candle["open"]))
    return clamp(body / candle_range)
