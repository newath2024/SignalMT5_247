from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SymbolStateModel:
    symbol: str
    state: str
    bias: str = "neutral"
    tf: str = "-"
    phase: str = "HTF_CONTEXT"
    reason: str = "waiting: HTF context"
    price: float | None = None
    score: float | None = None
    grade: str | None = None
    last_update: str | None = None
    scanned_at: float | None = None
    cooldown_remaining: int = 0
    cooldown_duration_sec: int = 0
    cooldown_until: str | None = None
    last_alert_time: str | None = None
    active_watch_id: str | None = None
    htf_context: str = "-"
    transition: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WatchPipelineModel:
    symbol: str
    direction: str
    htf_context: str
    ltf_tf: str
    state: str
    waiting_for: str
    ltf_sweep_status: str
    score: float | None = None
    grade: str | None = None
    zone_top: float | None = None
    zone_bottom: float | None = None
    armed_at: str | None = None
    bias: str | None = None
    watch_key: str | None = None
    status_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AlertRecordModel:
    time: str
    symbol: str
    tf: str
    direction: str
    alert_type: str
    reason: str
    entry: float | None = None
    sl: float | None = None
    status: str = "-"
    stage: str = "-"
    event_key: str = "-"
    channel: str = "-"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TimelineEventModel:
    timestamp: str
    event: str
    label: str
    phase: str | None = None
    state: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TimelineModel:
    symbol: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
