from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Zone:
    label: str
    timeframe: str
    type: str
    bias: str
    low: float
    high: float
    quality: float
    source_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        metadata = payload.pop("metadata", {})
        return {**payload, **metadata}


@dataclass(slots=True)
class SweepEvent:
    symbol: str
    timeframe: str
    bias: str
    sweep_index: int
    sweep_level: float
    structure_level: float
    swept_liquidity: list[str]
    quality: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        metadata = payload.pop("metadata", {})
        return {**payload, **metadata}


@dataclass(slots=True)
class IFVGZone:
    low: float
    high: float
    mode: str
    quality: float
    entry_quality: float
    source_index: int
    origin_candle_index: int
    origin_candle_high: float
    origin_candle_low: float
    entry_edge: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        metadata = payload.pop("metadata", {})
        return {**payload, **metadata}


@dataclass(slots=True)
class WatchSetup:
    symbol: str
    timeframe: str
    bias: str
    htf_context: str
    created_bar_index: int
    expiry_bar_index: int
    invalidation_price: float
    watch_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        metadata = payload.pop("metadata", {})
        return {**payload, **metadata}


@dataclass(slots=True)
class Signal:
    symbol: str
    timeframe: str
    bias: str
    setup_key: str
    score: float
    rr: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        metadata = payload.pop("metadata", {})
        return {**payload, **metadata}
