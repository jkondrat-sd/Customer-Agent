"""Tests for the eval retrieval script.

Validates labeled set loading and the BM25-only evaluation pipeline
(no API keys needed).
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest
from rank_bm25 import BM25Okapi

from retrieval.eval_retrieval import (
    _source_to_doc_id,
    evaluate_bm25_only,
    load_labeled_set,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def labeled_set_path(tmp_path: Path) -> Path:
    """Write a minimal labeled set to disk."""
    data = [
        {
            "question": "How do I reset my password?",
            "expected_doc_ids": ["password.md"],
            "expected_keywords": ["reset", "password"],
        },
        {
            "question": "What shipping options are available?",
            "expected_doc_ids": ["shipping.md"],
            "expected_keywords": ["shipping", "delivery"],
        },
    ]
    path = tmp_path / "test_labeled_set.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture()
def bm25_index_with_known_docs(tmp_path: Path) -> Path:
    """Build a BM25 index whose doc_ids match the labeled set fixture."""
    import hashlib

    texts = [
        "reset your password by clicking forgot password on the login page",
        "shipping options include standard express and overnight delivery",
        "billing and payment methods credit cards paypal",
    ]
    sources = ["password.md", "shipping.md", "billing.md"]
    doc_ids = [hashlib.sha256(s.encode()).hexdigest()[:16] for s in sources]

    tokenized = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenized)

    payload = {
        "bm25": bm25,
        "chunk_ids": [f"chunk_{i}" for i in range(len(texts))],
        "chunk_texts": texts,
        "chunk_sources": sources,
        "chunk_doc_ids": doc_ids,
    }
    path = tmp_path / "bm25.pkl"
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadLabeledSet:
    def test_loads_json(self, labeled_set_path: Path) -> None:
        items = load_labeled_set(labeled_set_path)
        assert len(items) == 2
        assert items[0]["question"] == "How do I reset my password?"

    def test_default_path_exists(self) -> None:
        """The project's actual labeled_set.json should exist."""
        path = Path(__file__).resolve().parent.parent / "evaluation" / "labeled_set.json"
        assert path.exists()
        items = load_labeled_set(path)
        assert len(items) >= 20  # Build guide says 20-30 pairs


class TestSourceToDocId:
    def test_deterministic(self) -> None:
        a = _source_to_doc_id("test.md")
        b = _source_to_doc_id("test.md")
        assert a == b

    def test_different_sources_different_ids(self) -> None:
        a = _source_to_doc_id("a.md")
        b = _source_to_doc_id("b.md")
        assert a != b


class TestEvaluateBM25Only:
    def test_computes_hit_rate(
        self,
        labeled_set_path: Path,
        bm25_index_with_known_docs: Path,
    ) -> None:
        items = load_labeled_set(labeled_set_path)
        metrics = evaluate_bm25_only(
            items,
            bm25_index_path=bm25_index_with_known_docs,
            top_k=5,
        )
        assert metrics["method"] == "bm25_only"
        assert metrics["total_questions"] == 2
        # Both questions should hit their target docs.
        assert metrics["hits"] == 2
        assert metrics["hit_rate_at_k"] == 1.0
