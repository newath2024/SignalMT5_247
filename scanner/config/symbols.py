from ..deps import mt5

WATCHLIST = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "USDCHF",
    "XAUUSD",
    "BTCUSD",
    "ETHUSD",
]

TIMEFRAME_MAP = {
    "H4": mt5.TIMEFRAME_H4,
    "H1": mt5.TIMEFRAME_H1,
    "M15": mt5.TIMEFRAME_M15,
    "M5": mt5.TIMEFRAME_M5,
    "M3": mt5.TIMEFRAME_M3,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
}

HISTORY_BARS = {
    "H4": 140,
    "H1": 160,
    "M15": 180,
    "M5": 220,
    "M3": 260,
    "D1": 15,
    "W1": 15,
}

CHART_WINDOWS = {"H4": 70, "H1": 90, "M15": 70, "M5": 90, "M3": 110}
ASIA_SESSION_UTC = (0, 8)
LONDON_SESSION_UTC = (8, 11)
