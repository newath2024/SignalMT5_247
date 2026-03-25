import unittest

from infra.config.diagnostics import build_startup_diagnostics
from infra.config.loader import load_raw_app_config, normalize_app_config, validate_config_payload


class ConfigLoaderTests(unittest.TestCase):
    def test_normalize_app_config_accepts_current_defaults(self):
        config = normalize_app_config(load_raw_app_config())
        self.assertEqual(config.app.name, "Liquidity Sniper")
        self.assertTrue(config.scanner.strict_ifvg)
        self.assertIn("M15", config.scanner.htf_timeframes)
        self.assertIn("H1", config.scanner.htf_timeframes)
        self.assertEqual(config.scanner.canonical_htf_timeframes, ["M15", "M30", "H1", "H4"])
        self.assertEqual(config.scanner.legacy_htf_timeframes, [])
        self.assertEqual(config.scanner.confirmation_limit, 2)
        self.assertIn("H1", config.scanner.confirmation_timeframes)

    def test_validate_config_payload_rejects_non_strict_ifvg(self):
        with self.assertRaisesRegex(ValueError, "strict_iFVG=true"):
            validate_config_payload({"scanner": {"strict_ifvg": False}})

    def test_validate_config_payload_rejects_unsupported_timeframe(self):
        with self.assertRaisesRegex(ValueError, "Only M15, M30, H1, and H4 are supported"):
            validate_config_payload({"scanner": {"htf_timeframes": ["D1"]}})

    def test_startup_diagnostics_reports_structure_timeframes(self):
        config = normalize_app_config(load_raw_app_config())

        diagnostics = build_startup_diagnostics(config)

        self.assertEqual(diagnostics["canonical_htf"], "M15, M30, H1, H4")
        self.assertEqual(diagnostics["legacy_htf_inputs"], "-")
        self.assertEqual(diagnostics["confirmation_timeframes"], "M3, M5, M15, H1")


if __name__ == "__main__":
    unittest.main()
