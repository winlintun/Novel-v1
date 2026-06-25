#!/usr/bin/env python3
"""Tests for src/utils/novel_slug.py — canonical novel id/slug/path resolution.

These tests pin the single-source-of-truth slug rules that unify
MemoryManager, VersionManager, the Flask web UI and the orchestrator's I/O
paths. The whole point: a "Daoist Master of Qing Xuan" folder (spaces + caps)
must produce ONE canonical novel_id and ONE space-free output path, and must
be found on disk whether the user passes the raw folder name or the slug.
"""

import unittest
from pathlib import Path

from src.utils.novel_slug import (
    is_canonical_novel_dir,
    novel_id_from_name,
    novel_id_from_slug,
    resolve_novel_input_dir,
    slug_from_novel_id,
    slugify_novel,
)


class TestSlugifyNovel(unittest.TestCase):
    def test_spaces_and_caps_become_hyphenated_lowercase(self):
        self.assertEqual(
            slugify_novel("Daoist Master of Qing Xuan"),
            "daoist-master-of-qing-xuan",
        )

    def test_already_slug_is_unchanged(self):
        self.assertEqual(slugify_novel("a-will-eternal1"), "a-will-eternal1")

    def test_idempotent(self):
        once = slugify_novel("Foo Bar Baz")
        twice = slugify_novel(once)
        self.assertEqual(once, twice)

    def test_collapses_repeated_separators(self):
        self.assertEqual(slugify_novel("Foo -- Bar__ Baz"), "foo-bar-baz")

    def test_strips_leading_trailing_dashes(self):
        self.assertEqual(slugify_novel("--foo bar--"), "foo-bar")

    def test_empty_falls_back_to_unknown(self):
        self.assertEqual(slugify_novel(""), "unknown")
        self.assertEqual(slugify_novel("   "), "unknown")

    def test_dots_are_replaced(self):
        # a dotfolder name should not survive as a path component
        self.assertEqual(slugify_novel(".versions"), "versions")


class TestNovelId(unittest.TestCase):
    def test_id_has_novel_prefix_and_underscore_body(self):
        self.assertEqual(
            novel_id_from_name("Daoist Master of Qing Xuan"),
            "novel_daoist_master_of_qing_xuan",
        )

    def test_id_matches_across_memory_and_version_managers(self):
        # MemoryManager._make_novel_id and VersionManager._get_or_create_novel
        # must produce the SAME id for the same novel — this is the regression
        # that broke glossary reattachment (AGENTS.md lesson #3).
        from src.memory.memory_manager import _make_novel_id
        self.assertEqual(_make_novel_id("a-will-eternal1"), "novel_a_will_eternal1")
        self.assertEqual(
            _make_novel_id("Daoist Master of Qing Xuan"),
            "novel_daoist_master_of_qing_xuan",
        )

    def test_novel_id_from_slug_and_reverse(self):
        self.assertEqual(novel_id_from_slug("a-will-eternal1"), "novel_a_will_eternal1")
        self.assertEqual(slug_from_novel_id("novel_a_will_eternal1"), "a-will-eternal1")

    def test_disk_folder_id_round_trip(self):
        # the on-disk folder 'a-will-eternal1' resolves to the DB id the
        # migration just consolidated all glossary rows onto.
        self.assertEqual(
            novel_id_from_name("a-will-eternal1"), "novel_a_will_eternal1"
        )


class TestResolveInputDir(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_raw_folder_with_spaces(self):
        (self.root / "Daoist Master of Qing Xuan").mkdir()
        (self.root / "Daoist Master of Qing Xuan" / "en").mkdir()
        (self.root / "Daoist Master of Qing Xuan" / "en" / "001.md").write_text("x")
        res = resolve_novel_input_dir(self.root, "Daoist Master of Qing Xuan")
        self.assertIsNotNone(res)
        self.assertTrue(res.is_dir())

    def test_finds_slug_folder_when_raw_passed(self):
        (self.root / "daoist-master-of-qing-xuan").mkdir()
        res = resolve_novel_input_dir(self.root, "Daoist Master of Qing Xuan")
        self.assertIsNotNone(res)
        self.assertEqual(res.name, "daoist-master-of-qing-xuan")

    def test_finds_raw_folder_when_slug_passed(self):
        (self.root / "Daoist Master of Qing Xuan").mkdir()
        res = resolve_novel_input_dir(self.root, "daoist-master-of-qing-xuan")
        self.assertIsNotNone(res)
        self.assertEqual(res.name, "Daoist Master of Qing Xuan")

    def test_returns_none_when_missing(self):
        self.assertIsNone(resolve_novel_input_dir(self.root, "no-such-novel"))

    def test_empty_name_returns_none(self):
        self.assertIsNone(resolve_novel_input_dir(self.root, ""))


class TestCanonicalNovelDirFilter(unittest.TestCase):
    def test_dotfolders_rejected(self):
        # the source of the phantom `novel_.versions` DB row
        self.assertFalse(is_canonical_novel_dir(".versions"))
        self.assertFalse(is_canonical_novel_dir(""))
        self.assertFalse(is_canonical_novel_dir("."))

    def test_real_novels_accepted(self):
        self.assertTrue(is_canonical_novel_dir("a-will-eternal1"))
        self.assertTrue(is_canonical_novel_dir("Daoist Master of Qing Xuan"))


class TestOrchestratorOutputPathNoSpaces(unittest.TestCase):
    """The orchestrator must NEVER write a path containing spaces, even when
    the novel folder name has them. _save_output derives the output dir from
    slugify_novel(self._current_novel), verified here at the slug level (the
    full _save_output needs Ollama wiring; we assert the contract the
    refactor introduced)."""

    def test_output_stem_uses_slug_not_raw_name(self):
        raw = "Daoist Master of Qing Xuan"
        slug = slugify_novel(raw)
        out = Path("data/output") / slug / f"{slug}_chapter_0001.mm.md"
        self.assertNotIn(" ", str(out))
        self.assertEqual(slug, "daoist-master-of-qing-xuan")


if __name__ == "__main__":
    unittest.main()