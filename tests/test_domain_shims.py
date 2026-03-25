import unittest

from domain.confirmation import detect_watch_candidates as canonical_detect_watch_candidates
from domain.context import detect_htf_context as canonical_detect_htf_context
from domain.engine import StrategyEngine as CanonicalStrategyEngine
from domain.strategy import StrategyEngine as CompatStrategyEngine
from domain.strategy.pipeline import phase_for_watch_status as compat_phase_for_watch_status
from domain.engine.pipeline import phase_for_watch_status as canonical_phase_for_watch_status
from domain.detectors.htf import detect_htf_context as compat_detect_htf_context
from domain.detectors.ltf import detect_watch_candidates as compat_detect_watch_candidates


class DomainShimTests(unittest.TestCase):
    def test_strategy_engine_compatibility_reexports_canonical_engine(self):
        self.assertIs(CompatStrategyEngine, CanonicalStrategyEngine)

    def test_detector_shims_reexport_canonical_detectors(self):
        self.assertIs(compat_detect_htf_context, canonical_detect_htf_context)
        self.assertIs(compat_detect_watch_candidates, canonical_detect_watch_candidates)

    def test_pipeline_shim_reexports_canonical_helper(self):
        self.assertIs(compat_phase_for_watch_status, canonical_phase_for_watch_status)


if __name__ == "__main__":
    unittest.main()
