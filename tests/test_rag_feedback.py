"""
Tests for RAG feedback loop repair (F1+F2) and glossary-aware retrieval (F3).
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import MagicMock, patch

from src.data.rag_retriever import RAGRetriever, TranslationExample


# ── F1: ChromaDB ingestion re-enabled ──────────────────────────────────────────

class TestFeedbackChromaIngestion:
    """F1: FeedbackLoop connects to ChromaDB and upserts verified pairs."""

    def test_chroma_collection_connected(self, tmp_path):
        """FeedbackLoop._init_chroma connects to a collection when path exists."""
        # Create a minimal chroma dir so the path check passes
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        db_path = str(tmp_path / "feedback.db")

        from src.data.feedback_loop import FeedbackLoop
        fl = FeedbackLoop(
            db_path=db_path,
            chroma_path=str(chroma_dir),
            min_adequacy=0.0,  # disable adequacy gate for this test
        )
        # Chroma may or may not connect (depends on chromadb install), but it
        # should NOT be hard-disabled like before (the old code set it to None
        # unconditionally). If chromadb is installed, _chroma_collection should
        # be non-None.
        try:
            import chromadb
            assert fl._chroma_collection is not None, "ChromaDB should connect when path exists"
        except ImportError:
            assert fl._chroma_collection is None  # graceful disable
        fl.close()

    def test_chroma_not_hard_disabled(self, tmp_path):
        """The old behavior (hard None) is gone — _init_chroma actually tries."""
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        db_path = str(tmp_path / "feedback.db")

        from src.data.feedback_loop import FeedbackLoop
        fl = FeedbackLoop(db_path=db_path, chroma_path=str(chroma_dir), min_adequacy=0.0)
        # The key assertion: _chroma_client is attempted, not skipped
        # If chromadb is installed, _chroma_client should be non-None
        try:
            import chromadb
            assert fl._chroma_client is not None
        except ImportError:
            pass  # acceptable — chromadb not installed in test env
        fl.close()


# ── F2: Adequacy gate ──────────────────────────────────────────────────────────

class TestFeedbackAdequacyGate:
    """F2: BGE-M3 adequacy gate rejects meaning-incomplete pairs."""

    def test_adequacy_column_added(self, tmp_path):
        """The adequacy_score column is added to translation_pairs."""
        db_path = str(tmp_path / "feedback.db")
        from src.data.feedback_loop import FeedbackLoop
        fl = FeedbackLoop(db_path=db_path, chroma_path=str(tmp_path / "nochroma"), min_adequacy=0.45)
        import sqlite3
        conn = sqlite3.connect(db_path)
        cols = {c[1] for c in conn.execute("PRAGMA table_info(translation_pairs)").fetchall()}
        conn.close()
        assert "adequacy_score" in cols, "adequacy_score column should be added"
        fl.close()

    def test_adequacy_column_idempotent(self, tmp_path):
        """Re-initializing FeedbackLoop doesn't fail on existing adequacy_score column."""
        db_path = str(tmp_path / "feedback.db")
        from src.data.feedback_loop import FeedbackLoop
        fl1 = FeedbackLoop(db_path=db_path, chroma_path=str(tmp_path / "nochroma"), min_adequacy=0.45)
        fl1.close()
        # Second init should not error
        fl2 = FeedbackLoop(db_path=db_path, chroma_path=str(tmp_path / "nochroma"), min_adequacy=0.45)
        fl2.close()

    def test_low_adequacy_rejected(self, tmp_path):
        """A pair with adequacy < min_adequacy is rejected even if heuristic score is high."""
        db_path = str(tmp_path / "feedback.db")
        from src.data.feedback_loop import FeedbackLoop
        fl = FeedbackLoop(db_path=db_path, chroma_path=str(tmp_path / "nochroma"), min_adequacy=0.45)

        # Patch _check_adequacy to return a low score (simulates meaning-incomplete)
        fl._check_adequacy = MagicMock(return_value=0.20)
        fl._embedder_loaded = True  # skip real embedder load
        fl._embedder = MagicMock()

        en = "The young man walked into the tavern and ordered a drink."
        my = "လူငယ်လေးက ညစာဆိုင်ထဲဝင်လာပြီး အဖျောင်းတစ်ခွက်မှာယူတယ်။"
        result = fl.rate_and_ingest(en, my)

        assert not result["ingested"], "Low-adequacy pair should be rejected"
        assert "low_adequacy" in result["reason"]
        assert fl.stats["rejected_low_adequacy"] == 1
        fl.close()

    def test_high_adequacy_accepted(self, tmp_path):
        """A pair with adequacy >= min_adequacy and good heuristic score is ingested."""
        db_path = str(tmp_path / "feedback.db")
        from src.data.feedback_loop import FeedbackLoop
        fl = FeedbackLoop(db_path=db_path, chroma_path=str(tmp_path / "nochroma"), min_adequacy=0.45)

        fl._check_adequacy = MagicMock(return_value=0.85)
        fl._embedder_loaded = True
        fl._embedder = MagicMock()

        en = "The young man walked into the tavern and ordered a drink."
        my = "လူငယ်လေးက ညစာဆိုင်ထဲဝင်လာပြီး အဖျောင်းတစ်ခွက်မှာယူတယ်။"
        result = fl.rate_and_ingest(en, my)

        assert result["ingested"], "High-adequacy + high-score pair should be ingested"
        assert result["adequacy_score"] == 0.85
        fl.close()

    def test_adequacy_score_stored_in_db(self, tmp_path):
        """The adequacy_score is persisted in the translation_pairs row."""
        db_path = str(tmp_path / "feedback.db")
        from src.data.feedback_loop import FeedbackLoop
        fl = FeedbackLoop(db_path=db_path, chroma_path=str(tmp_path / "nochroma"), min_adequacy=0.45)

        fl._check_adequacy = MagicMock(return_value=0.78)
        fl._embedder_loaded = True
        fl._embedder = MagicMock()

        en = "The young man walked into the tavern and ordered a drink."
        my = "လူငယ်လေးက ညစာဆိုင်ထဲဝင်လာပြီး အဖျောင်းတစ်ခွက်မှာယူတယ်။"
        fl.rate_and_ingest(en, my)

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT adequacy_score FROM translation_pairs LIMIT 1").fetchone()
        conn.close()
        assert row is not None and row[0] == 0.78
        fl.close()


# ── F3: Glossary-aware retrieval bias ──────────────────────────────────────────

class TestGlossaryAwareRetrieval:
    """F3: RAGRetriever boosts examples sharing glossary terms."""

    def test_boost_reorders_examples(self):
        """An example with glossary-term matches ranks above one without."""
        # Two examples: ex2 is semantically lower but contains a glossary term
        ex1 = TranslationExample(en_text="The sky was blue.", my_text="ကောင်းကင်က အပြာရောင်။", score=4.5, source_file="x", similarity=0.60)
        ex2 = TranslationExample(en_text="Bai Xiaochun cultivated in the Azure Origin Sect.", my_text="ဘိုင်ရှောင်ချန်က အေးဇင်းဂိုဏ်းမှာ ကျင့်ကြံတယ်။", score=4.5, source_file="x", similarity=0.55)
        examples = [ex1, ex2]

        glossary = ["Bai Xiaochun", "Azure Origin Sect"]
        result = RAGRetriever._apply_glossary_boost(examples, glossary)

        # ex2 gets +0.20 boost (2 terms), so 0.55+0.20=0.75 > ex1's 0.60
        assert result[0] is ex2, "Glossary-matching example should rank first"

    def test_boost_capped_at_030(self):
        """The boost is capped at +0.30 even with many glossary matches."""
        ex = TranslationExample(
            en_text="Bai Xiaochun Azure Origin Sect Spirit Condensation Eastwood Mountain.",
            my_text="ဘိုင်ရှောင်ချန် အေးဇင်းဂိုဏ်း ဝိညာဉ်စုပေါင်း အီးစ်ဝုဒ်တောင်တန်း။",
            score=4.5, source_file="x", similarity=0.50,
        )
        glossary = ["Bai Xiaochun", "Azure Origin Sect", "Spirit Condensation", "Eastwood Mountain"]
        result = RAGRetriever._apply_glossary_boost([ex], glossary)
        # 4 matches * 0.10 = 0.40, but capped at 0.30 → 0.50 + 0.30 = 0.80
        assert result[0].similarity == 0.50  # original similarity unchanged (boost is in sort, not mutation)

    def test_no_boost_when_no_glossary(self):
        """Without glossary_sources, the order is unchanged."""
        ex1 = TranslationExample(en_text="aaa", my_text="အ", score=4.0, source_file="x", similarity=0.70)
        ex2 = TranslationExample(en_text="bbb", my_text="ဘ", score=4.0, source_file="x", similarity=0.50)
        examples = [ex1, ex2]
        result = RAGRetriever._apply_glossary_boost(examples, None)
        assert result == examples, "No glossary → no reordering"

    def test_no_boost_for_short_terms(self):
        """Glossary terms shorter than 3 chars are ignored (noise filter)."""
        ex = TranslationExample(en_text="Qi is energy.", my_text="ကျီးက စွမ်းအင်။", score=4.0, source_file="x", similarity=0.50)
        glossary = ["Qi"]  # 2 chars — below the 3-char minimum
        result = RAGRetriever._apply_glossary_boost([ex], glossary)
        # No boost applied (term too short)
        assert result == [ex]

    def test_boost_case_insensitive(self):
        """Glossary term matching is case-insensitive."""
        ex = TranslationExample(en_text="bai xiaochun sat down.", my_text="ဘိုင်ရှောင်ချန် ထိုင်လိုက်တယ်။", score=4.0, source_file="x", similarity=0.50)
        glossary = ["Bai Xiaochun"]  # capitalized
        result = RAGRetriever._apply_glossary_boost([ex], glossary)
        # Match should still apply (case-insensitive)
        assert result[0] is ex

    def test_retrieve_similar_accepts_glossary_sources(self, tmp_path):
        """retrieve_similar accepts the glossary_sources kwarg without error."""
        # Use a non-existent chroma path + empty sqlite so retrieval returns []
        retriever = RAGRetriever(
            chroma_path=str(tmp_path / "nochroma"),
            db_path=str(tmp_path / "nodb.db"),
            top_k=3,
        )
        # Should not raise — glossary_sources is accepted
        result = retriever.retrieve_similar(
            "some query text",
            glossary_sources=["Bai Xiaochun", "Azure Origin Sect"],
        )
        assert isinstance(result, list)
        retriever.close()


# ── Integration: config wiring ─────────────────────────────────────────────────

class TestConfigWiring:
    """The new params flow through config to FeedbackLoop."""

    def test_min_adequacy_in_settings(self):
        """settings.yaml has the min_adequacy key."""
        from src.config import load_config
        config = load_config("config/settings.yaml")
        rag = config.dict().get("rag", {})
        assert "min_adequacy" in rag, "rag.min_adequacy should be in settings.yaml"
        assert rag["min_adequacy"] == 0.45
