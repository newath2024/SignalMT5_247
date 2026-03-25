"""Storage-oriented record models.

These DTO-like shapes back persistence adapters and timeline serialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


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
    events: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = ["AlertRecordModel", "TimelineEventModel", "TimelineModel"]
