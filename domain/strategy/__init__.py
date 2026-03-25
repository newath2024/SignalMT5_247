"""Compatibility namespace for strategy orchestration.

Canonical implementation lives in ``domain.engine``.
Safe to remove after import migration.
"""

from domain.engine import StrategyDecision, StrategyEngine

__all__ = ["StrategyDecision", "StrategyEngine"]
