from ..config.ltf import MIN_RR


def find_local_liquidity_levels(rates, bias, entry_price):
    levels = []
    if rates is None or len(rates) < 8:
        return levels

    highs = rates["high"]
    lows = rates["low"]
    for index in range(2, len(rates) - 2):
        if bias == "Long":
            level = float(highs[index])
            if level <= entry_price:
                continue
            if level >= float(highs[index - 1]) and level >= float(highs[index + 1]):
                levels.append((level, "Opposing liquidity"))
        else:
            level = float(lows[index])
            if level >= entry_price:
                continue
            if level <= float(lows[index - 1]) and level <= float(lows[index + 1]):
                levels.append((level, "Opposing liquidity"))
    return levels


def select_targets(entry_price, stop_loss, bias, all_htf_zones, trigger_rates):
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        return None

    levels = []
    levels.extend(find_local_liquidity_levels(trigger_rates, bias, entry_price))

    for zone in all_htf_zones:
        if bias == "Long":
            if zone["bias"] != "Short":
                continue
            level = zone["low"]
            if level > entry_price:
                levels.append((float(level), zone["label"]))
        else:
            if zone["bias"] != "Long":
                continue
            level = zone["high"]
            if level < entry_price:
                levels.append((float(level), zone["label"]))

    deduped = {}
    for level, label in levels:
        deduped[round(level, 8)] = (level, label)

    if bias == "Long":
        ordered = sorted(deduped.values(), key=lambda item: item[0])
        min_target = entry_price + MIN_RR * risk
        eligible = [item for item in ordered if item[0] >= min_target]
        if not eligible:
            return None
        tp1, tp1_label = eligible[0]
        tp2 = eligible[1][0] if len(eligible) > 1 else max(tp1 + risk, entry_price + 3.5 * risk)
    else:
        ordered = sorted(deduped.values(), key=lambda item: item[0], reverse=True)
        min_target = entry_price - MIN_RR * risk
        eligible = [item for item in ordered if item[0] <= min_target]
        if not eligible:
            return None
        tp1, tp1_label = eligible[0]
        tp2 = eligible[1][0] if len(eligible) > 1 else min(tp1 - risk, entry_price - 3.5 * risk)

    rr = abs(tp1 - entry_price) / risk
    return {
        "tp1": tp1,
        "tp2": tp2,
        "rr": rr,
        "target_label": tp1_label,
    }
