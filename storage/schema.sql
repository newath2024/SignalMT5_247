CREATE TABLE IF NOT EXISTS signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bias TEXT,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    event_key TEXT NOT NULL,
    reason TEXT,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_signal_events_created_at
    ON signal_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_signal_events_symbol_stage
    ON signal_events(symbol, stage);

CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    stage TEXT NOT NULL,
    channel TEXT NOT NULL,
    event_key TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_alert_history_created_at
    ON alert_history(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_history_symbol_stage
    ON alert_history(symbol, stage);

CREATE INDEX IF NOT EXISTS idx_alert_history_event_key
    ON alert_history(event_key, stage, channel, status);

CREATE TABLE IF NOT EXISTS rejection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bias TEXT,
    phase TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_rejection_history_created_at
    ON rejection_history(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rejection_history_symbol
    ON rejection_history(symbol);
