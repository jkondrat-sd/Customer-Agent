"""Tests for the document ingestion pipeline.

All external services (Pinecone, Gemini embeddings) are mocked so tests
run offline without API keys.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from retrieval.ingest import (
    Chunk,
    build_bm25_index,
    chunk_documents,
    load_documents,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_docs_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample Markdown docs."""
    (tmp_path / "doc_a.md").write_text(
        "# Alpha Document\n\nThis is the first document about alpha features.\n"
        "It covers setup and configuration for the alpha module.\n"
        "Alpha integrates with beta and gamma components.\n"
    )
    (tmp_path / "doc_b.md").write_text(
        "# Beta Document\n\nBeta documentation covering billing and payments.\n"
        "Payment methods include credit cards, ACH, and PayPal.\n"
        "Invoices are generated monthly.\n"
    )
    (tmp_path / "ignored.pdf").write_text("This should be skipped")
    return tmp_path


@pytest.fixture()
def sample_documents() -> list[dict[str, str]]:
    """Return pre-built documents for chunking tests."""
    return [
        {"doc_id": "doc1", "source": "test.md", "text": "A " * 300},
        {"doc_id": "doc2", "source": "test2.md", "text": "B " * 150},
    ]


# ---------------------------------------------------------------------------
# Tests: load_documents
# ---------------------------------------------------------------------------

class TestLoadDocuments:
    def test_loads_markdown_files(self, sample_docs_dir: Path) -> None:
        docs = load_documents(sample_docs_dir)
        assert len(docs) == 2
        sources = {d["source"] for d in docs}
        assert sources == {"doc_a.md", "doc_b.md"}

    def test_skips_unsupported_files(self, sample_docs_dir: Path) -> None:
        docs = load_documents(sample_docs_dir)
        sources = {d["source"] for d in docs}
        assert "ignored.pdf" not in sources

    def test_generates_deterministic_doc_ids(self, sample_docs_dir: Path) -> None:
        docs1 = load_documents(sample_docs_dir)
        docs2 = load_documents(sample_docs_dir)
        ids1 = [d["doc_id"] for d in docs1]
        ids2 = [d["doc_id"] for d in docs2]
        assert ids1 == ids2

    def test_empty_directory(self, tmp_path: Path) -> None:
        docs = load_documents(tmp_path)
        assert docs == []


# ---------------------------------------------------------------------------
# Tests: chunk_documents
# ---------------------------------------------------------------------------

class TestChunkDocuments:
    def test_produces_chunks(self, sample_documents: list[dict[str, str]]) -> None:
        chunks = chunk_documents(sample_documents, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 0
        assert all(isinstance(c, dict) for c in chunks)

    def test_chunk_ids_are_unique(self, sample_documents: list[dict[str, str]]) -> None:
        chunks = chunk_documents(sample_documents, chunk_size=100, chunk_overlap=20)
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_preserves_doc_id(self, sample_documents: list[dict[str, str]]) -> None:
        chunks = chunk_documents(sample_documents, chunk_size=100, chunk_overlap=20)
        doc_ids = {c["doc_id"] for c in chunks}
        assert doc_ids == {"doc1", "doc2"}

    def test_small_doc_produces_single_chunk(self) -> None:
        docs = [{"doc_id": "tiny", "source": "tiny.md", "text": "Hello world"}]
        chunks = chunk_documents(docs, chunk_size=400, chunk_overlap=50)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world"


# ---------------------------------------------------------------------------
# Tests: build_bm25_index
# ---------------------------------------------------------------------------

class TestBuildBM25Index:
    def test_creates_pickle_file(self, tmp_path: Path) -> None:
        chunks: list[Chunk] = [
            Chunk(chunk_id="c1", doc_id="d1", text="hello world", source="a.md"),
            Chunk(chunk_id="c2", doc_id="d1", text="foo bar baz", source="a.md"),
        ]
        output_path = tmp_path / "bm25.pkl"
        build_bm25_index(chunks, output_path)
        assert output_path.exists()

    def test_pickle_contains_expected_keys(self, tmp_path: Path) -> None:
        chunks: list[Chunk] = [
            Chunk(chunk_id="c1", doc_id="d1", text="test", source="a.md"),
        ]
        output_path = tmp_path / "bm25.pkl"
        build_bm25_index(chunks, output_path)

        with open(output_path, "rb") as f:
            payload = pickle.load(f)
        assert "bm25" in payload
        assert "chunk_ids" in payload
        assert "chunk_texts" in payload
        assert "chunk_sources" in payload
        assert "chunk_doc_ids" in payload

    def test_bm25_scores_are_valid(self, tmp_path: Path) -> None:
        # Need 3+ docs so BM25 IDF is non-zero for a term in only 1 doc.
        # With 2 docs and 1 match, IDF = log((2-1+0.5)/(1+0.5)) = log(1) = 0.
        chunks: list[Chunk] = [
            Chunk(chunk_id="c1", doc_id="d1", text="billing payment invoice", source="a.md"),
            Chunk(chunk_id="c2", doc_id="d2", text="shipping delivery tracking", source="b.md"),
            Chunk(chunk_id="c3", doc_id="d3", text="account setup password reset", source="c.md"),
        ]
        output_path = tmp_path / "bm25.pkl"
        bm25 = build_bm25_index(chunks, output_path)
        scores = bm25.get_scores(["billing"])
        assert len(scores) == 3
        # "billing" should score higher for chunk c1 than the others.
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]
