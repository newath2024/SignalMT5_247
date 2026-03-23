_analysis_cache = {}


def get_symbol_cache(symbol):
    return _analysis_cache.setdefault(symbol, {})


def get_cached_value(symbol, key):
    return get_symbol_cache(symbol).get(key)


def set_cached_value(symbol, key, value):
    get_symbol_cache(symbol)[key] = value
    return value


def build_timeframe_signature(snapshot, timeframe_names):
    rates = snapshot["rates"]
    return tuple(int(rates[name][-1]["time"]) for name in timeframe_names if name in rates and len(rates[name]))
