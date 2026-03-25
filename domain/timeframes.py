"""Canonical timeframe ordering helpers for structure-only strategy flow."""

from __future__ import annotations

from dataclasses import dataclass


TIMEFRAME_ORDER: tuple[str, ...] = ("M3", "M5", "M15", "M30", "H1", "H4")
TIMEFRAME_RANK: dict[str, int] = {name: index for index, name in enumerate(TIMEFRAME_ORDER)}


@dataclass(frozen=True)
class TimeframePolicy:
    htf_timeframes: list[str]
    confirmation_timeframes: list[str]
    confirmation_limit: int = 2

    def derive_confirmation_timeframes(self, active_htf: str) -> list[str]:
        return build_confirmation_timeframes(
            active_htf,
            self.confirmation_timeframes,
            limit=self.confirmation_limit,
        )


def normalize_timeframe_name(value: str) -> str:
    name = str(value or "").strip().upper()
    if name not in TIMEFRAME_RANK:
        raise ValueError(f"Unsupported timeframe: {value}")
    return name


def timeframe_rank(value: str) -> int:
    return TIMEFRAME_RANK[normalize_timeframe_name(value)]


def sort_timeframes(values: list[str] | tuple[str, ...]) -> list[str]:
    unique = {normalize_timeframe_name(item) for item in values}
    return sorted(unique, key=timeframe_rank)


def get_lower_timeframes(active_htf: str, available_timeframes: list[str] | tuple[str, ...]) -> list[str]:
    active_rank = timeframe_rank(active_htf)
    return [
        timeframe
        for timeframe in sort_timeframes(list(available_timeframes))
        if timeframe_rank(timeframe) < active_rank
    ]


def get_nearest_lower_timeframes(
    active_htf: str,
    available_timeframes: list[str] | tuple[str, ...],
    limit: int = 2,
) -> list[str]:
    lower = get_lower_timeframes(active_htf, available_timeframes)
    if limit <= 0:
        return lower
    return list(reversed(lower))[:limit]


def build_confirmation_timeframes(
    active_htf: str,
    available_timeframes: list[str] | tuple[str, ...],
    limit: int = 2,
) -> list[str]:
    """Derive valid confirmation frames for one active HTF."""
    nearest = get_nearest_lower_timeframes(active_htf, available_timeframes, limit=limit)
    return list(nearest)
