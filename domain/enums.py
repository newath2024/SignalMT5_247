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
    HTF_CONTEXT_FOUND = "htf_context_found"
    HTF_WEAK_CONTEXT = "htf_weak_context"
    SESSION_ONLY_CONTEXT = "session_only_context"
    NO_STRUCTURAL_BACKING = "no_structural_backing"
    AWAITING_LTF_SWEEP = "awaiting_ltf_sweep"
    SWEEP_DETECTED = "sweep_detected"
    ARMED = "armed"
    WAITING_MSS = "waiting_mss"
    AWAITING_IFVG = "awaiting_ifvg"
    TRIGGERED = "triggered"
    DEGRADED = "degraded"
    INVALIDATED = "invalidated"
    TWO_SIDED_LIQUIDITY_TAKEN = "two_sided_liquidity_taken"
    EXPIRED = "expired"
    AMBIGUOUS = "ambiguous"
    CONFIRMED = "confirmed"
    COOLDOWN = "cooldown"
    REJECTED = "rejected"
    ERROR = "error"


class SetupPhase(str, Enum):
    HTF_CONTEXT = "HTF_CONTEXT"
    LTF_SWEEP = "LTF_SWEEP"
    NARRATIVE = "NARRATIVE"
    WAITING_MSS = "WAITING_MSS"
    WAITING_IFVG = "WAITING_IFVG"
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
