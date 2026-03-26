import unittest

from services.symbol_registry import SymbolRegistry


class SymbolRegistryTests(unittest.TestCase):
    def test_suggest_symbols_matches_normalized_tokens(self):
        registry = SymbolRegistry(["XAUUSD", "BTCUSD", "US30.cash"])

        suggestions = registry.suggest_symbols("us30 cash")

        self.assertEqual(["US30.CASH"], suggestions)

    def test_alias_conflicting_with_configured_symbol_is_rejected(self):
        with self.assertRaises(ValueError):
            SymbolRegistry(["XAUUSD"], aliases={"xau usd": "XAUUSD"})

    def test_duplicate_alias_to_different_targets_is_rejected(self):
        with self.assertRaises(ValueError):
            SymbolRegistry(["XAUUSD", "BTCUSD"], aliases={"metal": "XAUUSD", "metal ": "BTCUSD"})


if __name__ == "__main__":
    unittest.main()
