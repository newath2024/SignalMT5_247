from ..data.cache import build_timeframe_signature, get_cached_value, get_symbol_cache, set_cached_value


def get_symbol_state(symbol):
    return get_symbol_cache(symbol)


def get_signature(symbol, key):
    return get_cached_value(symbol, key)


def set_signature(symbol, key, value):
    return set_cached_value(symbol, key, value)


__all__ = ["get_symbol_state", "get_signature", "set_signature", "build_timeframe_signature"]
