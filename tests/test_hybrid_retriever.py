"""Tests for the hybrid retriever.

Pinecone calls are mocked; BM25 uses a real pickled index built in fixtures.
Tests validate merge/dedupe logic and score normalization.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest
from rank_bm25 import BM25Okapi

from retrieval.hybrid_retriever import (
    RetrievalResult,
    _normalize_scores,
    merge_and_dedupe,
    sparse_search,
)
from retrieval.utils import tokenize


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def bm25_index_path(tmp_path: Path) -> Path:
    """Create a minimal BM25 index for testing."""
    texts = [
        "how to reset your password and recover account access",
        "billing payment methods credit card paypal invoice",
        "shipping delivery tracking order status",
        "return refund policy 30 days money back",
        "two factor authentication 2FA security setup",
    ]
    tokenized = [tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized)

    payload = {
        "bm25": bm25,
        "chunk_ids": [f"chunk_{i}" for i in range(len(texts))],
        "chunk_texts": texts,
        "chunk_sources": [f"doc_{i}.md" for i in range(len(texts))],
        "chunk_doc_ids": [f"doc_{i}" for i in range(len(texts))],
    }
    path = tmp_path / "test_bm25.pkl"
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    return path


# ---------------------------------------------------------------------------
# Tests: tokenizer
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_lowercases(self) -> None:
        assert tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self) -> None:
        assert tokenize("hello, world!") == ["hello", "world"]

    def test_empty_string(self) -> None:
        assert tokenize("") == []


# ---------------------------------------------------------------------------
# Tests: sparse_search
# ---------------------------------------------------------------------------

class TestSparseSearch:
    def test_returns_relevant_results(self, bm25_index_path: Path) -> None:
        results = sparse_search("password reset", bm25_index_path=bm25_index_path, top_k=3)
        assert len(results) > 0
        # Top result should be the password/account chunk.
        assert "password" in results[0]["text"]

    def test_respects_top_k(self, bm25_index_path: Path) -> None:
        results = sparse_search("password", bm25_index_path=bm25_index_path, top_k=2)
        assert len(results) <= 2

    def test_method_is_sparse(self, bm25_index_path: Path) -> None:
        results = sparse_search("billing", bm25_index_path=bm25_index_path, top_k=3)
        for r in results:
            assert r["method"] == "sparse"


# ---------------------------------------------------------------------------
# Tests: _normalize_scores
# ---------------------------------------------------------------------------

class TestNormalizeScores:
    def test_normalizes_to_zero_one(self) -> None:
        results: list[RetrievalResult] = [
            RetrievalResult(chunk_id="a", doc_id="d1", text="", source="", score=10.0, method="test"),
            RetrievalResult(chunk_id="b", doc_id="d2", text="", source="", score=5.0, method="test"),
            RetrievalResult(chunk_id="c", doc_id="d3", text="", source="", score=0.0, method="test"),
        ]
        normed = _normalize_scores(results)
        scores = [r["score"] for r in normed]
        assert max(scores) == 1.0
        assert min(scores) == 0.0

    def test_handles_identical_scores(self) -> None:
        results: list[RetrievalResult] = [
            RetrievalResult(chunk_id="a", doc_id="d1", text="", source="", score=5.0, method="test"),
            RetrievalResult(chunk_id="b", doc_id="d2", text="", source="", score=5.0, method="test"),
        ]
        normed = _normalize_scores(results)
        # Identical scores → all normalize to 1.0 (equally best).
        assert len(normed) == 2
        assert all(r["score"] == 1.0 for r in normed)

    def test_empty_input(self) -> None:
        assert _normalize_scores([]) == []


# ---------------------------------------------------------------------------
# Tests: merge_and_dedupe
# ---------------------------------------------------------------------------

class TestMergeAndDedupe:
    def test_deduplicates_by_chunk_id(self) -> None:
        dense: list[RetrievalResult] = [
            RetrievalResult(chunk_id="shared", doc_id="d1", text="shared text", source="a.md", score=0.9, method="dense"),
            RetrievalResult(chunk_id="dense_only", doc_id="d2", text="dense", source="b.md", score=0.7, method="dense"),
        ]
        sparse: list[RetrievalResult] = [
            RetrievalResult(chunk_id="shared", doc_id="d1", text="shared text", source="a.md", score=0.8, method="sparse"),
            RetrievalResult(chunk_id="sparse_only", doc_id="d3", text="sparse", source="c.md", score=0.6, method="sparse"),
        ]
        merged = merge_and_dedupe(dense, sparse)
        ids = [r["chunk_id"] for r in merged]
        assert ids.count("shared") == 1
        assert "dense_only" in ids
        assert "sparse_only" in ids

    def test_shared_chunk_gets_combined_score(self) -> None:
        dense: list[RetrievalResult] = [
            RetrievalResult(chunk_id="x", doc_id="d1", text="", source="", score=0.8, method="dense"),
        ]
        sparse: list[RetrievalResult] = [
            RetrievalResult(chunk_id="x", doc_id="d1", text="", source="", score=0.6, method="sparse"),
        ]
        # Both have max score in their respective sets, so normalized to 1.0 each
        # score = 1.0 * 0.5 + 1.0 * 0.5 = 1.0 (since single-item sets)
        merged = merge_and_dedupe(dense, sparse, dense_weight=0.5, sparse_weight=0.5)
        shared = [r for r in merged if r["chunk_id"] == "x"][0]
        assert shared["score"] == pytest.approx(1.0)

    def test_method_is_hybrid(self) -> None:
        dense: list[RetrievalResult] = [
            RetrievalResult(chunk_id="a", doc_id="d1", text="", source="", score=1.0, method="dense"),
        ]
        sparse: list[RetrievalResult] = [
            RetrievalResult(chunk_id="b", doc_id="d2", text="", source="", score=1.0, method="sparse"),
        ]
        merged = merge_and_dedupe(dense, sparse)
        for r in merged:
            assert r["method"] == "hybrid"

    def test_sorted_descending(self) -> None:
        dense: list[RetrievalResult] = [
            RetrievalResult(chunk_id="low", doc_id="d1", text="", source="", score=0.1, method="dense"),
            RetrievalResult(chunk_id="high", doc_id="d2", text="", source="", score=0.9, method="dense"),
        ]
        merged = merge_and_dedupe(dense, [])
        assert merged[0]["chunk_id"] == "high"
