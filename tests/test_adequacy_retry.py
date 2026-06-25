"""Tests for the per-chunk adequacy gate: unsampled scoring, bounded retry,
best-candidate selection, and block-mode rejection routing.

These exercise the retry loop wired into TranslationPipeline._translate_chunks.
The orchestrator has heavy lazy-loaded agents, so we construct a pipeline with
default config and inject simple mock agents via the private backing attributes
that the @property getters cache. Tests run in a temp cwd so the per-chunk
session/checkpoint file writes never touch the repo.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from src.config.models import AppConfig
from src.pipeline.orchestrator import TranslationPipeline

# Valid Myanmar so _calc_myanmar_ratio clears the 0.7 gate (not rejected/aborted).
MM_GOOD = "ဤသည် မြန်မာဘာသာဖြင့် ရေးသားထားသော စာသားဖြစ်သည်။"


def _adq(score, checked=True):
    issues = [] if score >= 0.45 else [{"type": "low_adequacy", "source": "x", "best_sim": score}]
    return {"checked": checked, "score": score, "issues": issues, "threshold": 0.45}


class TestAdequacyRetry(unittest.TestCase):
    def setUp(self):
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._prev_cwd)

    def _make_pipeline(self, action, adq_side_effect, translate_side_effect,
                       min_score=0.45, max_retries=1):
        cfg = AppConfig()
        cfg.translation_pipeline.mode = "single_stage"
        cfg.translation_pipeline.use_adequacy_gate = True
        cfg.translation_pipeline.adequacy_action = action
        cfg.translation_pipeline.adequacy_min_score = min_score
        cfg.translation_pipeline.adequacy_max_retries = max_retries

        p = TranslationPipeline(cfg)
        p._current_novel = None
        p._current_chapter = None
        p._memory_manager = None

        translator = MagicMock()
        translator.translate_paragraph.side_effect = translate_side_effect
        p._translator = translator

        mm_checker = MagicMock()
        mm_checker.check_quality.return_value = {"score": 95, "passed": True, "issues": []}
        p._myanmar_checker = mm_checker

        checker = MagicMock()
        checker.check_adequacy.side_effect = adq_side_effect
        checker.check_model_collapse.return_value = []
        checker.check_glossary_consistency.return_value = []
        p._checker = checker

        fb = MagicMock()
        fb.rate_and_ingest.return_value = {"ingested": False}
        p._feedback_loop = fb

        return p

    def test_retry_keeps_best_candidate(self):
        """Low adequacy on first attempt → re-translate; the higher-adequacy
        second candidate is the one committed to output."""
        p = self._make_pipeline(
            action="retry",
            adq_side_effect=[_adq(0.30), _adq(0.90)],
            translate_side_effect=[MM_GOOD + " A", MM_GOOD + " B"],
        )
        translated, metrics = p._translate_chunks(["source paragraph one."])

        self.assertEqual(p._translator.translate_paragraph.call_count, 2)
        self.assertEqual(translated[0], MM_GOOD + " B")          # best adequacy kept
        self.assertEqual(metrics[0]["adequacy_score"], 0.90)

    def test_retry_stops_once_adequate(self):
        """A first attempt that already clears the threshold is not retried."""
        p = self._make_pipeline(
            action="retry",
            adq_side_effect=[_adq(0.80)],
            translate_side_effect=[MM_GOOD],
        )
        translated, metrics = p._translate_chunks(["source."])

        self.assertEqual(p._translator.translate_paragraph.call_count, 1)
        self.assertEqual(metrics[0]["adequacy_score"], 0.80)

    def test_retries_are_bounded(self):
        """Persistently low adequacy retries exactly max_retries+1 times — no
        unbounded loop (NO HANGING)."""
        p = self._make_pipeline(
            action="block",
            adq_side_effect=[_adq(0.20), _adq(0.25), _adq(0.22)],
            translate_side_effect=[MM_GOOD + " 1", MM_GOOD + " 2", MM_GOOD + " 3"],
            max_retries=2,
        )
        translated, metrics = p._translate_chunks(["source."])

        self.assertEqual(p._translator.translate_paragraph.call_count, 3)  # 1 + 2 retries
        # Best of the three low candidates (0.25) is what gets recorded.
        self.assertEqual(metrics[0]["adequacy_score"], 0.25)

    def test_warn_mode_does_not_retry(self):
        """warn mode records the score but never re-translates, even when low."""
        p = self._make_pipeline(
            action="warn",
            adq_side_effect=[_adq(0.10)],
            translate_side_effect=[MM_GOOD],
        )
        translated, metrics = p._translate_chunks(["source."])

        self.assertEqual(p._translator.translate_paragraph.call_count, 1)
        self.assertEqual(metrics[0]["adequacy_score"], 0.10)

    # ── Deterministic hard-defect (Latin fused into Myanmar) ──────────────────

    def test_hard_defect_triggers_retry_even_when_adequacy_ok(self):
        """A Latin-in-Myanmar leak (e.g. 'ဟan') re-translates even though
        adequacy is high, and the clean candidate is preferred."""
        defective = MM_GOOD + " ဖြစ်နေဟan"   # Latin 'an' fused to Myanmar
        p = self._make_pipeline(
            action="retry",
            adq_side_effect=[_adq(0.90), _adq(0.90)],   # adequacy is fine both times
            translate_side_effect=[defective, MM_GOOD],
        )
        translated, metrics = p._translate_chunks(["source."])

        self.assertEqual(p._translator.translate_paragraph.call_count, 2)
        self.assertEqual(translated[0], MM_GOOD)        # clean candidate kept

    def test_placeholder_name_triggers_retry(self):
        """A '??' placeholder (the cross-lingual name failure) re-translates and
        the clean candidate is kept — even though adequacy is high."""
        with_placeholder = MM_GOOD + " သူ့နာမည်မှာ ??"
        p = self._make_pipeline(
            action="retry",
            adq_side_effect=[_adq(0.90), _adq(0.90)],
            translate_side_effect=[with_placeholder, MM_GOOD],
        )
        translated, metrics = p._translate_chunks(["source."])
        self.assertEqual(p._translator.translate_paragraph.call_count, 2)
        self.assertEqual(translated[0], MM_GOOD)

    def test_persistent_hard_defect_is_bounded(self):
        """A defect that survives every attempt does not loop unboundedly."""
        defective = MM_GOOD + " ဖြစ်နေဟan"
        p = self._make_pipeline(
            action="retry",
            adq_side_effect=[_adq(0.90), _adq(0.90)],
            translate_side_effect=[defective, defective],
            max_retries=1,
        )
        translated, metrics = p._translate_chunks(["source."])

        self.assertEqual(p._translator.translate_paragraph.call_count, 2)  # 1 + 1 retry
        # Content is preserved (not dropped) even though the chunk is rejected.
        self.assertEqual(translated[0], defective)


if __name__ == "__main__":
    unittest.main()
