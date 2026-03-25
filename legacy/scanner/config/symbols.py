from ..deps import mt5

WATCHLIST = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "EURJPY",
    "GBPJPY",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    "XAUUSD",
    "BTCUSD",
    "ETHUSD",
]

TIMEFRAME_MAP = {
    "H4": mt5.TIMEFRAME_H4,
    "H1": mt5.TIMEFRAME_H1,
    "M30": mt5.TIMEFRAME_M30,
    "M15": mt5.TIMEFRAME_M15,
    "M5": mt5.TIMEFRAME_M5,
    "M3": mt5.TIMEFRAME_M3,
}

HISTORY_BARS = {
    "H4": 140,
    "H1": 160,
    "M30": 180,
    "M15": 180,
    "M5": 220,
    "M3": 260,
}

CHART_WINDOWS = {"H4": 70, "H1": 90, "M30": 85, "M15": 70, "M5": 90, "M3": 110}
SESSION_DEFINITIONS: dict[str, dict[str, object]] = {}
