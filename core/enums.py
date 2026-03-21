from enum import Enum


class AlertMode(str, Enum):
    ARMED_ONLY = "armed_only"
    CONFIRMED_ONLY = "confirmed_only"
    BOTH = "both"


class ScanPhase(str, Enum):
    SYSTEM = "system"
    CONNECTION = "connection"
    HTF = "htf"
    WATCH = "watch"
    SIGNAL = "signal"
    ALERT = "alert"
    STORAGE = "storage"


class SignalStage(str, Enum):
    WATCH_ARMED = "watch_armed"
    CONFIRMED_SIGNAL = "confirmed_signal"


class SymbolHealth(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WATCH_ARMED = "watch_armed"
    SIGNAL_CONFIRMED = "signal_confirmed"
    COOLDOWN = "cooldown"
    REJECTED = "rejected"
    DELIVERY_FAILED = "delivery_failed"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
