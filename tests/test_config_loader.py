import unittest

from infra.config.diagnostics import build_startup_diagnostics
from infra.config.loader import load_raw_app_config, normalize_app_config, validate_config_payload


class ConfigLoaderTests(unittest.TestCase):
    def test_normalize_app_config_accepts_current_defaults(self):
        config = normalize_app_config(load_raw_app_config())
        self.assertEqual(config.app.name, "Liquidity Sniper")
        self.assertTrue(config.scanner.strict_ifvg)
        self.assertIn("H1", config.scanner.htf_timeframes)
        self.assertEqual(config.scanner.canonical_htf_timeframes, ["H1", "H4"])
        self.assertEqual(config.scanner.legacy_htf_timeframes, ["M30"])
        self.assertIn("M3", config.scanner.ltf_timeframes)

    def test_validate_config_payload_rejects_non_strict_ifvg(self):
        with self.assertRaisesRegex(ValueError, "strict_iFVG=true"):
            validate_config_payload({"scanner": {"strict_ifvg": False}})

    def test_validate_config_payload_rejects_unsupported_timeframe(self):
        with self.assertRaisesRegex(ValueError, "Only M30, H1, and H4 are supported"):
            validate_config_payload({"scanner": {"htf_timeframes": ["D1"]}})

    def test_startup_diagnostics_split_canonical_and_legacy_htf(self):
        config = normalize_app_config(load_raw_app_config())

        diagnostics = build_startup_diagnostics(config)

        self.assertEqual(diagnostics["canonical_htf"], "H1, H4")
        self.assertEqual(diagnostics["legacy_htf_inputs"], "M30")


if __name__ == "__main__":
    unittest.main()
