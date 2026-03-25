"""OHLC snapshot cache boundary.

Currently this is a pass-through cache. It exists so future optimization can
switch to candle-keyed reuse without changing scan orchestration.
"""

from __future__ import annotations

from typing import Any


class OhlcSnapshotCache:
    def get(self, symbol: str) -> dict[str, Any] | None:
        return None

    def put(self, symbol: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        return snapshot
