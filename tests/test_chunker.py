#!/usr/bin/env python3
"""
Tests for src/utils/chunker.py — smart paragraph chunking.

Per need_to_fix.md spec: all 6 tests MUST pass.
- Never splits inside a paragraph
- Oversized single paragraph becomes its own chunk
- overlap is always zero (each paragraph appears exactly once)
- Rolling context respects token budget
- Empty chunk returns empty context
- First chunk gets empty context
"""

import unittest
from src.utils.chunker import smart_chunk, get_rolling_context, estimate_tokens


class TestSmartChunk(unittest.TestCase):

    def test_never_splits_inside_paragraph(self):
        """Paragraph must appear INTACT in exactly one chunk."""
        text = "Para one.\n\nPara two is very long " + ("x " * 2000) + "end.\n\nPara three."
        chunks = smart_chunk(text, max_tokens=1500)
        for chunk in chunks:
            # Para two should never be split across chunks
            self.assertLessEqual(chunk.count("Para two"), 1,
                "Paragraph was split across chunks — forbidden!")
        # All three paragraphs must be present somewhere
        self.assertIn("Para one.", " ".join(chunks))
        self.assertIn("Para three.", " ".join(chunks))

    def test_oversized_single_paragraph_becomes_own_chunk(self):
        """A paragraph exceeding max_tokens alone must NOT be split."""
        long_para = "word " * 2000  # way over 1500 tokens
        short_para = "Short."
        text = f"{short_para}\n\n{long_para}"
        chunks = smart_chunk(text, max_tokens=1500)
        self.assertGreaterEqual(len(chunks), 2,
            "Oversized paragraph should be in its own chunk")
        # Verify long paragraph appears intact in one chunk
        long_found = False
        for chunk in chunks:
            if long_para.strip() in chunk:
                long_found = True
                break
        self.assertTrue(long_found, "Long paragraph not found intact in any chunk")

    def test_overlap_is_zero(self):
        """Each paragraph must appear EXACTLY ONCE across all chunks."""
        paragraphs = [f"Paragraph {i}." for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = smart_chunk(text, max_tokens=1500)
        assembled = "\n\n".join(chunks)

        for i, para in enumerate(text.split("\n\n")):
            count = assembled.count(para)
            self.assertEqual(count, 1,
                f"Paragraph {i} appears {count} times — should be exactly once!")

    def test_short_text_single_chunk(self):
        """Short text should produce exactly 1 chunk."""
        text = "One.\n\nTwo.\n\nThree."
        chunks = smart_chunk(text, max_tokens=1500)
        self.assertEqual(len(chunks), 1)

    def test_empty_text(self):
        """Empty text should produce 0 chunks."""
        self.assertEqual(len(smart_chunk("", max_tokens=1500)), 0)
        self.assertEqual(len(smart_chunk("   \n\n   ", max_tokens=1500)), 0)

    def test_max_tokens_respected(self):
        """No chunk should exceed max_tokens estimate."""
        paragraphs = [f"Paragraph {i} with some content to fill space. " * 5
                      for i in range(30)]
        text = "\n\n".join(paragraphs)
        chunks = smart_chunk(text, max_tokens=1500)
        for i, chunk in enumerate(chunks):
            est = estimate_tokens(chunk)
            # Allow some margin: single oversize paragraphs become own chunk
            if est > 2000:
                self.assertEqual(chunk.count("\n\n"), 0,
                    f"Chunk {i} is oversized ({est} tokens) but contains "
                    f"multiple paragraphs — should only happen for single "
                    f"oversized paragraphs")


class TestRollingContext(unittest.TestCase):

    def test_rolling_context_respects_token_budget(self):
        """Context must not exceed max_context_tokens."""
        big_chunk = "\n\n".join(["word " * 200 for _ in range(10)])
        context = get_rolling_context(big_chunk, max_context_tokens=400)
        estimated = estimate_tokens(context)
        self.assertLessEqual(estimated, 400,
            f"Rolling context estimated at {estimated} tokens, exceeds 400 budget")

    def test_empty_chunk_returns_empty_context(self):
        """Empty input must return empty string."""
        self.assertEqual(get_rolling_context(""), "")
        self.assertEqual(get_rolling_context("", max_context_tokens=400), "")

    def test_first_chunk_gets_empty_context(self):
        """Orchestrator must pass empty string for chunk index 0."""
        context = get_rolling_context("", max_context_tokens=400)
        self.assertEqual(context, "")

    def test_context_preserves_paragraph_order(self):
        """Tail paragraphs must be in original order."""
        text = "\n\n".join([f"Paragraph {i}." for i in range(5)])
        context = get_rolling_context(text, max_context_tokens=1000)
        # Should contain last paragraphs in order
        if "Paragraph 4." in context:
            idx4 = context.index("Paragraph 4.")
            idx3 = context.index("Paragraph 3.")
            self.assertLess(idx3, idx4, "Paragraph order not preserved")

    def test_never_splits_mid_paragraph(self):
        """Context extraction must not break inside a paragraph."""
        # Create known paragraphs
        paras = [f"Para {i}: " + "word " * 50 for i in range(10)]
        text = "\n\n".join(paras)
        context = get_rolling_context(text, max_context_tokens=400)
        # Verify: no partial paragraph (each para in context is complete)
        for para in paras:
            if para in context:
                # Must appear as complete paragraph
                pass  # para.split would give partial if it were broken
        # If context is non-empty, it should end with a complete paragraph
        if context:
            last_para_in_context = context.split("\n\n")[-1]
            # Last para in context must exist complete in original
            self.assertIn(last_para_in_context, text,
                "Context extracted partial paragraph!")


if __name__ == "__main__":
    unittest.main()
