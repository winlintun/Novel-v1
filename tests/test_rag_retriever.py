"""Tests for RAGRetriever similarity conversion and SQLite fallback.

Covers:
- L2-distance -> cosine-similarity conversion (collection uses Chroma's default
  squared-L2 space; similarity must be 1 - distance/2, not 1 - distance).
- Fallback to SQLite keyword retrieval when Chroma's best match is below
  min_similarity (sentence-corpus vs paragraph-query granularity mismatch).
"""
from src.data.rag_retriever import RAGRetriever, TranslationExample


def _ex(sim):
    return TranslationExample(en_text="en", my_text="mm", score=3.0,
                              source_file="f", similarity=sim)


def _retriever(chroma, sqlite, min_similarity=0.3):
    r = RAGRetriever.__new__(RAGRetriever)  # bypass __init__ (no I/O)
    r.top_k = 3
    r.novel_filter = None
    r.min_similarity = min_similarity
    r._chroma_collection = object()  # truthy
    r._retrieve_from_chroma = lambda q, k, n: chroma
    r._retrieve_from_sqlite = lambda q, k, n: sqlite
    return r


def test_strong_chroma_is_used():
    out = _retriever([_ex(0.6)], [_ex(0.9)]).retrieve_similar("q")
    assert [e.similarity for e in out] == [0.6]  # chroma kept, no fallback


def test_weak_chroma_falls_back_to_sqlite():
    out = _retriever([_ex(0.1)], [_ex(0.44)]).retrieve_similar("q")
    assert [e.similarity for e in out] == [0.44]  # sqlite used


def test_weak_chroma_and_empty_sqlite_returns_chroma():
    out = _retriever([_ex(0.1)], []).retrieve_similar("q")
    assert [e.similarity for e in out] == [0.1]  # last resort: weak chroma


def test_no_chroma_uses_sqlite():
    out = _retriever([], [_ex(0.3)]).retrieve_similar("q")
    assert [e.similarity for e in out] == [0.3]


class _FakeCollection:
    name = "alignment_pairs"

    def query(self, **kwargs):
        # one hit at squared-L2 distance 0.6  ->  cosine 1 - 0.6/2 = 0.7
        return {
            "ids": [["a"]],
            "metadatas": [[{"my_text": "mm", "auto_score": "3.0", "source_file": ""}]],
            "documents": [["en"]],
            "distances": [[0.6]],
        }


def test_l2_distance_converted_to_cosine():
    r = RAGRetriever.__new__(RAGRetriever)
    r.min_score = 2.5
    r._verify_chroma = lambda: True
    r._embed_query = lambda t: [0.1] * 1024
    r._chroma_collection = _FakeCollection()
    out = r._retrieve_from_chroma("q", 3, None)
    assert len(out) == 1
    assert abs(out[0].similarity - 0.7) < 1e-9  # 1 - 0.6/2, NOT 1 - 0.6 (=0.4)
