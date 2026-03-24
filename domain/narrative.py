from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class LiquidityEvent:
    label: str
    side: str
    bias: str
    timeframe: str
    sweep_index: int
    timestamp: int | None
    sweep_price: float
    reference_price: float | None
    close_price: float
    reclaimed: bool
    sweep_depth: float
    sweep_depth_ratio: float
    wick_ratio: float
    body_ratio: float
    quality: float
    is_external_liquidity: bool = True
    is_primary_candidate: bool = False
    close_reclaim: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NarrativeEvent:
    index: int
    event_type: str
    timestamp: int | None
    bias: str | None = None
    label: str | None = None
    side: str | None = None
    price: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = payload.pop("event_type")
        return payload


@dataclass(slots=True)
class NarrativeAnalysis:
    symbol: str
    timeframe: str
    bias: str
    state: str
    narrative_bias: str
    narrative_quality: float
    ready_for_signal: bool
    has_two_sided_sweep: bool = False
    ambiguous: bool = False
    primary_sweep: dict[str, Any] | None = None
    opposite_sweep: dict[str, Any] | None = None
    first_external_sweep: dict[str, Any] | None = None
    second_external_sweep: dict[str, Any] | None = None
    displacement: dict[str, Any] | None = None
    mss: dict[str, Any] | None = None
    ifvg: dict[str, Any] | None = None
    invalidation_reason: str | None = None
    status_reason: str | None = None
    timeline: list[dict[str, Any]] = field(default_factory=list)
    sweep_candidates: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
