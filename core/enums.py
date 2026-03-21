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


class SetupState(str, Enum):
    IDLE = "idle"
    CONTEXT_FOUND = "context_found"
    ARMED = "armed"
    WAITING_MSS = "waiting_mss"
    CONFIRMED = "confirmed"
    COOLDOWN = "cooldown"
    REJECTED = "rejected"
    ERROR = "error"


class SetupPhase(str, Enum):
    HTF_CONTEXT = "HTF_CONTEXT"
    LTF_SWEEP = "LTF_SWEEP"
    WAITING_MSS = "WAITING_MSS"
    IFVG_VALIDATION = "IFVG_VALIDATION"
    READY = "READY"
    ALERT_SENT = "ALERT_SENT"


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
