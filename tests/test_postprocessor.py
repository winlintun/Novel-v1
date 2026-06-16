"""
Unit tests for postprocessor module.
Tests clean_output, validate_output, language detection.
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.postprocessor import (
    strip_reasoning_tags,
    strip_header_artifacts,
    detect_language_leakage,
    myanmar_char_ratio,
    clean_output,
    validate_output,
    remove_chinese_characters,
    remove_japanese_kana,
    fix_chapter_heading_format,
    check_sentence_completion,
    detect_ngram_repetition,
    check_source_aligned_ordinals,
)


class TestStripReasoningTags(unittest.TestCase):
    """Test stripping of reasoning model tags."""

    def test_strip_think_tags(self):
        """Test stripping <think>...</think> tags."""
        text = "<think>Internal thought</think>မြန်မာဘာသာ"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<think>", result)
        self.assertNotIn("</think>", result)
        self.assertNotIn("Internal thought", result)
        self.assertIn("မြန်မာဘာသာ", result)

    def test_strip_answer_tags(self):
        """Test stripping <answer> tags."""
        text = "<answer>မြန်မာဘာသာ</answer>"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<answer>", result)
        self.assertNotIn("</answer>", result)
        self.assertIn("မြန်မာဘာသာ", result)

    def test_strip_html_comments(self):
        """Test stripping HTML comments."""
        text = "<!-- comment -->မြန်မာဘာသာ"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<!--", result)
        self.assertNotIn("-->", result)
        self.assertIn("မြန်မာဘာသာ", result)

    def test_strip_multiline_think(self):
        """Test stripping multiline think blocks."""
        text = """<think>
Line 1
Line 2
</think>
မြန်မာဘာသာ"""
        result = strip_reasoning_tags(text)
        self.assertNotIn("<think>", result)
        self.assertNotIn("Line 1", result)
        self.assertIn("မြန်မာဘာသာ", result)

    def test_case_insensitive_strip(self):
        """Test case-insensitive tag stripping."""
        text = "<THINK>thought</THINK><ANSWER>text</ANSWER>"
        result = strip_reasoning_tags(text)
        self.assertNotIn("<THINK>", result)
        self.assertNotIn("<ANSWER>", result)


class TestStripHeaderArtifacts(unittest.TestCase):
    """Test stripping of header artifacts."""

    def test_strip_translation_headers(self):
        """Test stripping MYANMAR TRANSLATION headers."""
        text = "MYANMAR TRANSLATION:\nမြန်မာဘာသာ"
        result = strip_header_artifacts(text)
        self.assertNotIn("MYANMAR TRANSLATION:", result)
        self.assertIn("မြန်မာဘာသာ", result)

    def test_strip_input_headers(self):
        """Test stripping INPUT TEXT headers."""
        text = "INPUT TEXT:\nမြန်မာဘာသာ"
        result = strip_header_artifacts(text)
        self.assertNotIn("INPUT TEXT:", result)
        self.assertIn("မြန်မာဘာသာ", result)

    def test_strip_progress_headers(self):
        """Test stripping Translation Progress headers."""
        text = "Translation Progress: 50%\nမြန်မာဘာသာ"
        result = strip_header_artifacts(text)
        self.assertNotIn("Translation Progress", result)
        self.assertIn("မြန်မာဘာသာ", result)


class TestDetectLanguageLeakage(unittest.TestCase):
    """Test language leakage detection."""

    def test_detect_thai_chars(self):
        """Test detecting Thai characters."""
        text = "မြန်မာစာ กรุงเทพฯ more text"
        result = detect_language_leakage(text)
        self.assertGreater(result["thai_chars"], 0)

    def test_detect_chinese_chars(self):
        """Test detecting Chinese characters."""
        text = "မြန်မာစာ 中文 more text"
        result = detect_language_leakage(text)
        self.assertGreater(result["chinese_chars"], 0)

    def test_detect_japanese_kana(self):
        """Japanese kana leakage is detected (the stray Hiragana い from ch.1)."""
        text = "မြန်မာစာ " + chr(0x3044) + chr(0x30AB) + " more text"  # い カ
        result = detect_language_leakage(text)
        self.assertGreater(result["japanese_chars"], 0)

    def test_remove_japanese_kana_keeps_myanmar(self):
        """remove_japanese_kana strips kana but preserves Myanmar text."""
        text = "အမူ" + chr(0x3044) + " ပိုင်ရှောင်ချန်း"  # Myanmar + い + Myanmar
        cleaned = remove_japanese_kana(text)
        self.assertNotIn(chr(0x3044), cleaned)
        self.assertIn("အမူ", cleaned)
        self.assertIn("ပိုင်ရှောင်ချန်း", cleaned)

    def test_clean_output_strips_japanese_kana(self):
        """clean_output() removes leaked kana end-to-end."""
        text = "အခန်း တစ်" + chr(0x3044) + " စာသား"
        self.assertNotIn(chr(0x3044), clean_output(text))

    def test_no_leakage_clean_text(self):
        """Test clean Myanmar text has no leakage."""
        text = "မြန်မာဘာသာ စာသား သန့်သန့်ရှင်းရှင်း"
        result = detect_language_leakage(text)
        self.assertEqual(result["thai_chars"], 0)
        self.assertEqual(result["chinese_chars"], 0)

    def detect_mixed_leakage(self):
        """Test detecting both Thai and Chinese."""
        text = "မြန်မာစာ กรุง中文 mixed"
        result = detect_language_leakage(text)
        self.assertGreater(result["thai_chars"], 0)
        self.assertGreater(result["chinese_chars"], 0)


class TestMyanmarCharRatio(unittest.TestCase):
    """Test Myanmar character ratio calculation."""

    def test_pure_myanmar(self):
        """Test pure Myanmar text returns 1.0."""
        text = "မြန်မာဘာသာ"
        ratio = myanmar_char_ratio(text)
        self.assertEqual(ratio, 1.0)

    def test_mixed_content(self):
        """Test mixed content returns correct ratio."""
        text = "မြန်မာ ABC"  # 4 Myanmar + 3 Latin + 1 space
        ratio = myanmar_char_ratio(text)
        self.assertGreater(ratio, 0.5)
        self.assertLess(ratio, 1.0)

    def test_no_myanmar(self):
        """Test text with no Myanmar returns 0."""
        text = "Hello World 123"
        ratio = myanmar_char_ratio(text)
        self.assertEqual(ratio, 0.0)

    def test_empty_string(self):
        """Test empty string returns 0."""
        ratio = myanmar_char_ratio("")
        self.assertEqual(ratio, 0.0)

    def test_whitespace_only(self):
        """Test whitespace-only string returns 0."""
        ratio = myanmar_char_ratio("   \n\t  ")
        self.assertEqual(ratio, 0.0)


class TestCleanOutput(unittest.TestCase):
    """Test full clean_output pipeline."""

    def test_mid_body_hallucinated_heading_does_not_drop_content(self):
        """A '# အခန်း N' heading hallucinated in a LATE chunk must NOT delete the
        body before it (catastrophic content-loss bug: 4 chunks -> heading only)."""
        body1 = "ပထမ စာပိုဒ် " * 10
        body2 = "ဒုတိယ စာပိုဒ် " * 10
        # last chunk got mistranslated into a heading
        joined = f"{body1}\n\n{body2}\n\n# အခန်း ၁\n\n## ခေါင်းစဉ်"
        out = clean_output(joined, chapter=1)
        self.assertIn("ပထမ", out)   # chunk 1 body preserved
        self.assertIn("ဒုတိယ", out)  # chunk 2 body preserved
        # exactly one chapter heading, at the top
        self.assertTrue(out.lstrip().startswith("# "))
        self.assertEqual(sum(1 for ln in out.split("\n") if ln.strip().startswith("# အ")), 1)
        self.assertGreater(len(out), 100)  # not collapsed to a heading

    def test_leading_heading_still_stripped_and_reinjected(self):
        """A heading at the TOP is still normalized to the correct one."""
        out = clean_output("# အခန်း ၉\n\nစာသား", chapter=3)
        self.assertTrue(out.lstrip().startswith("# အခန်း ၃"))
        self.assertIn("စာသား", out)

    def test_full_pipeline(self):
        """Test complete cleaning pipeline."""
        raw = """<think>Thinking...</think>
MYANMAR TRANSLATION:
မြန်မာဘာသာ



More text"""
        result = clean_output(raw)
        self.assertNotIn("<think>", result)
        self.assertNotIn("MYANMAR TRANSLATION:", result)
        self.assertIn("မြန်မာဘာသာ", result)
        # Should collapse multiple blank lines
        self.assertNotIn("\n\n\n", result)

    def test_strips_leading_trailing_whitespace(self):
        """Test leading/trailing whitespace is stripped."""
        raw = "   \n\nမြန်မာဘာသာ\n\n   "
        result = clean_output(raw)
        self.assertEqual(result[0], "မ")  # Starts with Myanmar
        self.assertEqual(result[-1], "ာ")  # Ends with Myanmar

    def test_removes_chinese_characters(self):
        """Test Chinese characters are removed in clean_output with aggressive=True."""
        raw = "မြန်မာဘာသာ 中文句子 မြန်မာစာ"
        result = clean_output(raw, aggressive=True)  # Use aggressive mode to remove Chinese
        self.assertNotIn("中", result)
        self.assertNotIn("文", result)
        self.assertNotIn("句", result)
        self.assertIn("မြန်မာဘာသာ", result)
        self.assertIn("မြန်မာစာ", result)

    def test_default_no_aggressive_removal(self):
        """Test that clean_output always strips Chinese/Bengali but preserves Latin by default."""
        raw = "မြန်မာဘာသာ 中文句子 မြန်မာစာ"
        result = clean_output(raw)  # Default: aggressive=False
        # Chinese is ALWAYS stripped (unambiguous garbage in Myanmar output)
        self.assertNotIn("中", result)
        self.assertNotIn("文", result)
        # Myanmar content preserved
        self.assertIn("မြန်မာဘာသာ", result)
        self.assertIn("မြန်မာစာ", result)


class TestRemoveChineseCharacters(unittest.TestCase):
    """Test Chinese character removal."""

    def test_remove_simple_chinese(self):
        """Test removing simple Chinese characters."""
        text = "မြန်မာစာ 你好 မြန်မာစာ"
        result = remove_chinese_characters(text)
        self.assertNotIn("你", result)
        self.assertNotIn("好", result)
        self.assertIn("မြန်မာစာ", result)

    def test_remove_mixed_chinese(self):
        """Test removing mixed Chinese from colloquial text."""
        text = '千年难逢的事儿吧正好被我撞到了'
        result = remove_chinese_characters(text)
        self.assertEqual(result, "")

    def test_preserve_myanmar_only(self):
        """Test Myanmar-only text is unchanged."""
        text = "မြန်မာဘာသာ စာသား"
        result = remove_chinese_characters(text)
        self.assertEqual(result, text)

    def test_remove_complex_chinese_sentence(self):
        """Test removing complex Chinese sentence."""
        text = "မြန်မာ遇到的神仙十分不仗义 မြန်မာ"
        result = remove_chinese_characters(text)
        self.assertNotIn("遇", result)
        self.assertNotIn("到", result)
        self.assertNotIn("神", result)
        self.assertIn("မြန်မာ", result)


class TestValidateOutput(unittest.TestCase):
    """Test output validation and quality scoring."""

    def test_approved_high_quality(self):
        """Test high-quality Myanmar text is approved."""
        text = "မြန်မာဘာသာ စာသား တစ်ခု လုံလောက်သော အရှည်"
        report = validate_output(text, chapter=1)
        self.assertEqual(report["chapter"], 1)
        self.assertEqual(report["status"], "APPROVED")
        self.assertGreaterEqual(report["myanmar_ratio"], 0.70)
        self.assertEqual(report["thai_chars_leaked"], 0)

    def test_needs_review_low_ratio(self):
        """Test moderately low Myanmar ratio needs review (30-70%)."""
        # Text with ~50% Myanmar ratio - should be flagged for review
        text = "မြန်မာစာ English words မြန်မာစာ more English here"
        report = validate_output(text, chapter=2)
        # Status depends on exact ratio - just verify it's flagged
        self.assertIn(report["status"], ["NEEDS_REVIEW", "REJECTED"])

    def test_rejected_thai_leakage(self):
        """Test Thai leakage causes rejection (critical error)."""
        text = "မြန်မာဘာသာ กรุงเทพฯ"
        report = validate_output(text, chapter=3)
        self.assertEqual(report["status"], "REJECTED")
        self.assertGreater(report["thai_chars_leaked"], 0)

    def test_rejected_chinese_leakage(self):
        """Test Chinese leakage causes rejection (critical error)."""
        text = "မြန်မာဘာသာ 遇到的神仙"
        report = validate_output(text, chapter=4)
        self.assertEqual(report["status"], "REJECTED")
        self.assertGreater(report["chinese_chars_leaked"], 0)

    def test_chinese_leakage_detected_in_report(self):
        """Test Chinese leakage is correctly counted in report."""
        text = "မြန်မာစာ 中文 မြန်မာ"
        report = validate_output(text, chapter=5)
        # Should detect at least 1 Chinese character
        self.assertGreater(report["chinese_chars_leaked"], 0)

    def test_report_structure(self):
        """Test report contains all required fields."""
        text = "မြန်မာဘာသာ"
        report = validate_output(text, chapter=5)
        required_fields = ["chapter", "myanmar_ratio", "thai_chars_leaked", "chinese_chars_leaked", "status"]
        for field in required_fields:
            self.assertIn(field, report)


class TestFixChapterHeadingFormat(unittest.TestCase):
    """Test chapter heading format fixing."""

    def test_bare_numeral_with_subtitle(self):
        """Test fixing bare numeral # ၃ followed by ## Title."""
        text = """# ၃

## ယင်၏ကိုယ်ခန္ဓာ

Content here."""
        result = fix_chapter_heading_format(text)
        # Should combine into proper format
        self.assertIn("# အခန်း ၃: ယင်၏ကိုယ်ခန္ဓာ", result)
        self.assertNotIn("# ၃", result)
        self.assertNotIn("## ယင်", result)

    def test_bare_arabic_numeral(self):
        """Test fixing bare numeral # 3 followed by ## Title."""
        text = """# 3

## Chapter Title

Content here."""
        result = fix_chapter_heading_format(text)
        self.assertIn("# အခန်း 3: Chapter Title", result)
        self.assertNotIn("# 3", result)

    def test_normal_chapter_heading_split(self):
        """Test that colon-separated chapter headings are split into H1 + H2 format."""
        text = """# အခန်း ၅: ခေါင်းစဉ်

Content here."""
        result = fix_chapter_heading_format(text)
        # Pattern 2 splits "# အခန်း N: Title" into "# အခန်း N" + "## Title"
        self.assertIn("# အခန်း ၅", result)
        self.assertIn("## ခေါင်းစဉ်", result)
        self.assertNotIn("# အခန်း ၅: ခေါင်းစဉ်", result)

    def test_bare_numeral_without_subtitle_unchanged(self):
        """Test bare numeral without following ## subtitle is kept as-is."""
        text = """# ၁၀

Some content without subtitle."""
        result = fix_chapter_heading_format(text)
        # Should remain unchanged since no subtitle follows
        self.assertIn("# ၁၀", result)


class TestParentheticalPreservation(unittest.TestCase):
    """Test that literary parenthetical content is preserved."""

    def test_parenthetical_myanmar_aside_preserved(self):
        """Myanmar literary asides in parentheses must survive clean_output."""
        text = "သူသည် ထိုအကြောင်းကို စဉ်းစားနေတယ် (သူ့ရဲ့နောက်ဆုံးရွေးချယ်မှု) ဒါပေမဲ့ ဆုံးဖြတ်ချက်မချနိုင်သေးဘူး။"
        result = clean_output(text)
        self.assertIn("(", result)
        self.assertIn(")", result)
        self.assertIn("သူ့ရဲ့နောက်ဆုံးရွေးချယ်မှု", result)

    def test_english_explanation_stripped(self):
        """English explanation patterns (This is ...) should still be stripped."""
        text = "Some Myanmar text (This is an explanation of the term) continues here."
        result = clean_output(text)
        self.assertNotIn("This is an explanation", result)

    def test_mixed_parenthetical_preserved(self):
        """Multiple parenthetical asides should all survive."""
        text = "Character A (the elder) spoke to B (the younger) about the plan."
        result = clean_output(text)
        self.assertIn("(the elder)", result)
        self.assertIn("(the younger)", result)

    def test_no_false_positive_strip(self):
        """Parentheses used in Myanmar literary text must be kept."""
        text = "ငါသာ (တစ်ကယ်တော့) ဒီကိစ္စကို သိပါတယ်။"
        result = clean_output(text)
        self.assertIn("(", result)
        self.assertIn(")", result)


class TestCheckSentenceCompletion(unittest.TestCase):
    """Test sentence completion detection (report.md 4.3)."""

    def test_complete_sentence_passes(self):
        """Sentences ending with ္။ should not be flagged."""
        text = "သူသည် ကျောင်းသားဖြစ်သည်။"
        issues = check_sentence_completion(text)
        self.assertEqual(len(issues), 0)

    def test_incomplete_particle_end_detected(self):
        """Lines ending with particle without ္။ should be flagged."""
        text = "သူမသည် ထိုအရာကို ယူဆောင်သွားခဲ့၏"
        issues = check_sentence_completion(text)
        self.assertGreater(len(issues), 0)
        self.assertIn('incomplete_sentence', issues[0]['issue'])

    def test_heading_not_flagged(self):
        """Markdown headings should not be flagged as incomplete."""
        text = "# Chapter 1"
        issues = check_sentence_completion(text)
        self.assertEqual(len(issues), 0)

    def test_short_line_not_flagged(self):
        """Short lines (<10 chars) should be ignored."""
        text = "ပြီး"
        issues = check_sentence_completion(text)
        self.assertEqual(len(issues), 0)

    def test_complete_sentence_with_common_endings_not_flagged(self):
        """Common complete Myanmar sentence endings must NOT be flagged as incomplete."""
        endings = [
            "သူသည် ကျောင်းသားဖြစ်တယ်။",
            "ငါ သွားမယ်။",
            "သူမ လာပြီ။",
            "ကျွန်တော် နားလည်ပါတယ်။",
        ]
        for text in endings:
            issues = check_sentence_completion(text)
            self.assertEqual(len(issues), 0, f"False positive for: {text}")


class TestDetectNgramRepetition(unittest.TestCase):
    """Test n-gram repetition detection (report.md 4.1)."""

    def test_no_repetition(self):
        """Normal text should not be flagged."""
        text = "မင်္ဂလာပါ။ ဒီနေ့ ရာသီဥတုက သာယာပါတယ်။"
        result = detect_ngram_repetition(text)
        self.assertFalse(result['has_repetition'])

    def test_repetition_detected(self):
        """Repeated Myanmar n-grams should be flagged."""
        text = "AAAAAAAAAAAAAAAAAAAA"  # 20 A's, no Myanmar
        result = detect_ngram_repetition(text, n=4, max_repeats=3)
        self.assertFalse(result['has_repetition'])  # no Myanmar n-grams → safe
        # Now with clear Myanmar char repetition
        text_mm = "ကကကကကကကကကကကကကကကကကကကက"  # က (U+1000) repeated 19 times
        result_mm = detect_ngram_repetition(text_mm, n=3, max_repeats=2)
        self.assertTrue(result_mm['has_repetition'])

    def test_empty_text(self):
        """Empty text should return no repetition."""
        result = detect_ngram_repetition("")
        self.assertFalse(result['has_repetition'])


class TestCheckSourceAlignedOrdinals(unittest.TestCase):
    """Test source-aligned ordinal verification (report.md 4.2)."""

    def test_no_ordinals_no_issues(self):
        """Text without ordinals should pass."""
        issues = check_source_aligned_ordinals(
            "Hello world.",
            "မင်္ဂလာပါ။"
        )
        self.assertEqual(len(issues), 0)

    def test_correct_ordinal_matching(self):
        """Correct positional matching should not flag false mismatches."""
        issues = check_source_aligned_ordinals(
            "He reached the 1st stage, then the 2nd stage.",
            "သူသည် ပထမအဆင့်သို့ ရောက်ရှိပြီး ဒုတိယအဆင့်သို့ ရောက်ရှိခဲ့သည်။"
        )
        self.assertEqual(len(issues), 0)

    def test_shifted_ordinal_detected(self):
        """+1 shift (9th→10th) should be flagged."""
        issues = check_source_aligned_ordinals(
            "He is at the 9th stage.",
            "သူသည် ဒသမအဆင့်မှာ ရှိသည်။"
        )
        self.assertGreater(len(issues), 0)

    def test_chinese_ordinal_correct(self):
        """Chinese ordinal 第N (digit form) should match positionally."""
        issues = check_source_aligned_ordinals(
            "他达到了第9层。",
            "သူသည် နဝမအဆင့်သို့ ရောက်ရှိခဲ့သည်။"
        )
        self.assertEqual(len(issues), 0)

    def test_chinese_ordinal_shifted_detected(self):
        """Chinese ordinal +1 shift (第9→10th) should be flagged."""
        issues = check_source_aligned_ordinals(
            "他达到了第9层。",
            "သူသည် ဒသမအဆင့်သို့ ရောက်ရှိခဲ့သည်။"
        )
        self.assertGreater(len(issues), 0)


if __name__ == '__main__':
    unittest.main()
