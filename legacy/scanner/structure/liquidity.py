from ..config.ltf import EXTERNAL_LIQUIDITY_LEVELS


def find_swept_external_liquidity(bias, sweep_high, sweep_low, sweep_close, reference_levels, point):
    swept = []
    for label in EXTERNAL_LIQUIDITY_LEVELS[bias]:
        level = reference_levels.get(label)
        if level is None:
            continue
        if bias == "Long":
            if sweep_low < level - point * 2 and sweep_close > level:
                swept.append(label)
        else:
            if sweep_high > level + point * 2 and sweep_close < level:
                swept.append(label)
    return swept
