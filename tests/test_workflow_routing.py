"""Tests for workflow routing: way1 and way2."""

import argparse
import tempfile
import unittest
from pathlib import Path

from src.cli.commands import _resolve_workflow, _apply_workflow_config
from src.config import load_config_from_dict


class TestWorkflowRouting(unittest.TestCase):
    def test_resolve_workflow_explicit_way1(self):
        args = argparse.Namespace(workflow="way1", lang=None, input_file=None)
        self.assertEqual(_resolve_workflow(args), "way1")

    def test_resolve_workflow_from_lang_en(self):
        args = argparse.Namespace(workflow=None, lang="en", input_file=None)
        self.assertEqual(_resolve_workflow(args), "way1")

    def test_resolve_workflow_from_lang_zh(self):
        args = argparse.Namespace(workflow=None, lang="zh", input_file=None)
        self.assertEqual(_resolve_workflow(args), "way2")

    def test_resolve_workflow_auto_detect_english_input(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("This is an English chapter. The hero walked into the valley. The wind blew through the trees as he looked around at the ancient ruins before him.")
            path = f.name
        try:
            args = argparse.Namespace(workflow=None, lang=None, input_file=path, novel=None)
            self.assertEqual(_resolve_workflow(args), "way1")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_resolve_workflow_auto_detect_chinese_input(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("这是一个中文章节。主角走进了山谷，灵气翻涌，天地间灵气弥漫。他在这个修仙世界里不断修炼，从筑基到金丹，一路披荆斩棘，终成一代仙尊。")
            path = f.name
        try:
            args = argparse.Namespace(workflow=None, lang=None, input_file=path, novel=None)
            self.assertEqual(_resolve_workflow(args), "way2")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_apply_way1_overrides_direct_en_to_mm(self):
        cfg = load_config_from_dict({
            "project": {},
            "translation_pipeline": {}
        })
        out = _apply_workflow_config(cfg, "way1")
        self.assertEqual(out.project.source_language, "en-US")
        self.assertEqual(out.translation_pipeline.mode, "single_stage")
        self.assertFalse(out.translation_pipeline.use_reflection)

    def test_apply_way2_overrides_pivot_cn_to_en_to_mm(self):
        cfg = load_config_from_dict({
            "project": {},
            "translation_pipeline": {}
        })
        out = _apply_workflow_config(cfg, "way2")
        self.assertEqual(out.project.source_language, "zh-CN")
        self.assertEqual(out.translation_pipeline.mode, "two_stage")


class TestGenerateGlossaryRouting(unittest.TestCase):
    """Tests for --generate-glossary standalone command validation."""

    def _make_args(self, **kwargs) -> argparse.Namespace:
        defaults = dict(
            ui=False, test=False, generate_glossary=False,
            view_file=None, review_file=None, auto_promote=False, stats=False,
            novel=None, input_file=None,
            chapter=None, all=False, chapter_range=None,
            config=None
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_generate_glossary_novel_no_chapter_accepted(self):
        """--novel X --generate-glossary must NOT raise even without --chapter/--all."""
        from src.cli.parser import validate_arguments
        args = self._make_args(generate_glossary=True, novel="my-novel")
        try:
            validate_arguments(args)
        except SystemExit as e:
            self.fail(f"validate_arguments raised SystemExit unexpectedly: {e}")

    def test_novel_without_chapter_and_no_generate_glossary_rejected(self):
        """--novel X alone (no chapter, no generate-glossary) must still be rejected."""
        from src.cli.parser import validate_arguments
        args = self._make_args(novel="my-novel")
        with self.assertRaises(SystemExit):
            validate_arguments(args)

    def test_generate_glossary_standalone_does_not_run_translation(self):
        """When --generate-glossary is standalone (no chapter/all), main() must not reach translation."""
        # Patch run_glossary_generation to succeed and run_translation_pipeline to detect if called
        import unittest.mock as mock
        import importlib
        import src.main as main_mod
        importlib.reload(main_mod)

        with mock.patch("src.main.run_glossary_generation", return_value=0) as mock_gen, \
             mock.patch("src.main._run_translation_with_opts") as mock_trans, \
             mock.patch("src.main.parse_arguments") as mock_parse, \
             mock.patch("src.main.validate_arguments"):

            mock_parse.return_value = argparse.Namespace(
                clean=False, rebuild_meta=False, ui=False, test=False,
                view_file=None, review_file=None, auto_promote=False, stats=False,
                generate_glossary=True, novel="my-novel",
                chapter=None, all=False, chapter_range=None, input_file=None,
                config=None, model=None, mode=None, output_dir=None
            )
            main_mod.main()

        mock_gen.assert_called_once()
        mock_trans.assert_not_called()


if __name__ == "__main__":
    unittest.main()
