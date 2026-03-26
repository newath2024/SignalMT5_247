import unittest

from services.runtime_state import RuntimeState


class RuntimeStateTests(unittest.TestCase):
    def test_get_symbol_state_returns_deep_copy(self):
        state = RuntimeState(["EURUSD"])
        payload = {
            "symbol": "EURUSD",
            "detail": {
                "timeline": ["first"],
            },
        }
        state.update_symbol_state(payload)

        snapshot = state.get_symbol_state("EURUSD")
        snapshot["detail"]["timeline"].append("mutated")

        fresh = state.get_symbol_state("EURUSD")
        self.assertEqual(["first"], fresh["detail"]["timeline"])

    def test_list_symbol_states_returns_deep_copies(self):
        state = RuntimeState(["EURUSD"])
        state.seed_symbol_states(
            [
                {
                    "symbol": "EURUSD",
                    "detail": {
                        "markers": {"state": "armed"},
                    },
                }
            ]
        )

        rows = state.list_symbol_states(["EURUSD"])
        rows[0]["detail"]["markers"]["state"] = "mutated"

        fresh = state.get_symbol_state("EURUSD")
        self.assertEqual("armed", fresh["detail"]["markers"]["state"])


if __name__ == "__main__":
    unittest.main()
