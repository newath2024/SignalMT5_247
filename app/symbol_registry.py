from __future__ import annotations

from collections.abc import Iterable
from difflib import get_close_matches


def _normalize_token(raw: str | None) -> str:
    value = str(raw or "").strip().upper()
    for separator in (" ", "/", "-", "_"):
        value = value.replace(separator, "")
    return value


class SymbolRegistry:
    def __init__(self, configured_symbols: Iterable[str], aliases: dict[str, str] | None = None):
        self._symbols: list[str] = []
        self._normalized_to_symbol: dict[str, str] = {}
        for raw_symbol in configured_symbols:
            symbol = str(raw_symbol).strip().upper()
            normalized = _normalize_token(symbol)
            if not symbol or not normalized:
                continue
            if normalized in self._normalized_to_symbol:
                raise ValueError(f"Duplicate configured symbol detected: {symbol}")
            self._symbols.append(symbol)
            self._normalized_to_symbol[normalized] = symbol

        self._aliases: dict[str, str] = {}
        for raw_alias, raw_target in (aliases or {}).items():
            alias = _normalize_token(raw_alias)
            target = self.normalize_symbol(raw_target)
            if not alias:
                continue
            if target is None:
                raise ValueError(f"Alias target is not a configured symbol: {raw_alias} -> {raw_target}")
            self._aliases[alias] = target

    def get_all_symbols(self) -> list[str]:
        return list(self._symbols)

    def get_aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def normalize_symbol(self, raw: str | None) -> str | None:
        normalized = _normalize_token(raw)
        if not normalized:
            return None
        if normalized in self._normalized_to_symbol:
            return self._normalized_to_symbol[normalized]
        return self._aliases.get(normalized)

    def is_valid_symbol(self, raw: str | None) -> bool:
        return self.normalize_symbol(raw) is not None

    def suggest_symbols(self, raw: str | None, limit: int = 5) -> list[str]:
        normalized = _normalize_token(raw)
        if not normalized:
            return self.get_all_symbols()[:limit]
        choices = self.get_all_symbols()
        direct = [symbol for symbol in choices if symbol.startswith(normalized)]
        if direct:
            return direct[:limit]
        return get_close_matches(normalized, choices, n=limit, cutoff=0.35)
