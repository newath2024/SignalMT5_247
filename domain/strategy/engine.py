"""Compatibility shim for strategy runtime wrapper.

Canonical implementation lives in ``domain.engine.strategy``.
Safe to remove after import migration.
"""

from domain.engine.strategy import StrategyDecision, StrategyEngine

__all__ = ["StrategyDecision", "StrategyEngine"]
