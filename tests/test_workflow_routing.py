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
            f.write("This is an English chapter. The hero walked into the valley.")
            path = f.name
        try:
            args = argparse.Namespace(workflow=None, lang=None, input_file=path, novel=None)
            self.assertEqual(_resolve_workflow(args), "way1")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_resolve_workflow_auto_detect_chinese_input(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("这是一个中文章节。主角走进了山谷，灵气翻涌。")
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

    def test_apply_way2_overrides_pivot_cn_to_en_to_mm(self):
        cfg = load_config_from_dict({
            "project": {},
            "translation_pipeline": {}
        })
        out = _apply_workflow_config(cfg, "way2")
        self.assertEqual(out.project.source_language, "zh-CN")
        self.assertEqual(out.translation_pipeline.mode, "two_stage")


if __name__ == "__main__":
    unittest.main()
