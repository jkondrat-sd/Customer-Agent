"""Retrieval evaluation script.

Computes hit-rate@k for three retrieval strategies against the labeled set
in ``evaluation/labeled_set.json``:

1. **BM25 only** — sparse lexical search (baseline)
2. **Dense only** — Pinecone semantic search (baseline)
3. **Hybrid + rerank** — the full pipeline (should beat both)

This is the *only* place where single-method retrieval is acceptable
(skill.md §1 exemption for baseline comparison).

Usage::

    uv run python -m retrieval.eval_retrieval
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class EvalItem(TypedDict):
    question: str
    expected_doc_ids: list[str]
    expected_keywords: list[str]


class EvalMetrics(TypedDict):
    method: str
    hit_rate_at_k: float
    total_questions: int
    hits: int


def _source_to_doc_id(source: str) -> str:
    """Reproduce the deterministic doc_id from ingest.load_documents."""
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def load_labeled_set(path: str | Path | None = None) -> list[EvalItem]:
    """Load the labeled evaluation set from disk."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "evaluation" / "labeled_set.json"
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_bm25_only(
    labeled_set: list[EvalItem],
    *,
    bm25_index_path: str | Path | None = None,
    top_k: int = 5,
) -> EvalMetrics:
    """Evaluate sparse-only retrieval (BM25 baseline)."""
    from retrieval.hybrid_retriever import sparse_search

    if bm25_index_path is None:
        from config import settings
        bm25_index_path = settings.bm25_index_path

    hits = 0
    for item in labeled_set:
        results = sparse_search(
            item["question"],
            bm25_index_path=bm25_index_path,
            top_k=top_k,
        )
        expected_ids = {_source_to_doc_id(s) for s in item["expected_doc_ids"]}
        retrieved_ids = {r["doc_id"] for r in results}
        if expected_ids & retrieved_ids:
            hits += 1

    return EvalMetrics(
        method="bm25_only",
        hit_rate_at_k=hits / len(labeled_set) if labeled_set else 0.0,
        total_questions=len(labeled_set),
        hits=hits,
    )


def evaluate_dense_only(
    labeled_set: list[EvalItem],
    *,
    pinecone_api_key: str | None = None,
    pinecone_index_name: str | None = None,
    embedding_api_key: str | None = None,
    embedding_model: str | None = None,
    top_k: int = 5,
) -> EvalMetrics:
    """Evaluate dense-only retrieval (Pinecone baseline)."""
    from retrieval.hybrid_retriever import dense_search
    from config import settings

    pinecone_api_key = pinecone_api_key or settings.pinecone_api_key
    pinecone_index_name = pinecone_index_name or settings.pinecone_index_name
    embedding_api_key = embedding_api_key or settings.gemini_api_key
    embedding_model = embedding_model or settings.embedding_model

    hits = 0
    for item in labeled_set:
        results = dense_search(
            item["question"],
            api_key=pinecone_api_key,
            index_name=pinecone_index_name,
            embedding_api_key=embedding_api_key,
            embedding_model=embedding_model,
            top_k=top_k,
        )
        expected_ids = {_source_to_doc_id(s) for s in item["expected_doc_ids"]}
        retrieved_ids = {r["doc_id"] for r in results}
        if expected_ids & retrieved_ids:
            hits += 1

    return EvalMetrics(
        method="dense_only",
        hit_rate_at_k=hits / len(labeled_set) if labeled_set else 0.0,
        total_questions=len(labeled_set),
        hits=hits,
    )


def evaluate_hybrid_rerank(
    labeled_set: list[EvalItem],
    *,
    top_k: int = 20,
    rerank_top_n: int = 5,
    pinecone_api_key: str | None = None,
    pinecone_index_name: str | None = None,
    embedding_api_key: str | None = None,
    embedding_model: str | None = None,
    bm25_index_path: str | Path | None = None,
) -> EvalMetrics:
    """Evaluate the full hybrid + rerank pipeline."""
    from retrieval.hybrid_retriever import hybrid_search
    from retrieval.reranker import rerank

    hits = 0
    for item in labeled_set:
        candidates = hybrid_search(
            item["question"],
            top_k=top_k,
            pinecone_api_key=pinecone_api_key,
            pinecone_index_name=pinecone_index_name,
            embedding_api_key=embedding_api_key,
            embedding_model=embedding_model,
            bm25_index_path=bm25_index_path,
        )
        reranked = rerank(item["question"], candidates, top_n=rerank_top_n)

        expected_ids = {_source_to_doc_id(s) for s in item["expected_doc_ids"]}
        retrieved_ids = {r["doc_id"] for r in reranked}
        if expected_ids & retrieved_ids:
            hits += 1

    return EvalMetrics(
        method="hybrid_rerank",
        hit_rate_at_k=hits / len(labeled_set) if labeled_set else 0.0,
        total_questions=len(labeled_set),
        hits=hits,
    )


def run_evaluation(
    *,
    bm25_only: bool = True,
    dense_only: bool = False,
    hybrid_rerank: bool = True,
    labeled_set_path: str | Path | None = None,
) -> list[EvalMetrics]:
    """Run selected evaluation strategies and print a comparison table.

    Set *dense_only* to ``True`` only when Pinecone credentials are
    configured — it is ``False`` by default so BM25 baseline and local
    hybrid tests can run offline.
    """
    labeled_set = load_labeled_set(labeled_set_path)
    logger.info("Loaded %d evaluation items", len(labeled_set))

    results: list[EvalMetrics] = []

    if bm25_only:
        logger.info("Running BM25-only evaluation...")
        metrics = evaluate_bm25_only(labeled_set)
        results.append(metrics)
        logger.info("BM25-only hit-rate@5: %.2f%% (%d/%d)",
                     metrics["hit_rate_at_k"] * 100, metrics["hits"], metrics["total_questions"])

    if dense_only:
        logger.info("Running dense-only evaluation...")
        metrics = evaluate_dense_only(labeled_set)
        results.append(metrics)
        logger.info("Dense-only hit-rate@5: %.2f%% (%d/%d)",
                     metrics["hit_rate_at_k"] * 100, metrics["hits"], metrics["total_questions"])

    if hybrid_rerank:
        logger.info("Running hybrid+rerank evaluation...")
        metrics = evaluate_hybrid_rerank(labeled_set)
        results.append(metrics)
        logger.info("Hybrid+rerank hit-rate@5: %.2f%% (%d/%d)",
                     metrics["hit_rate_at_k"] * 100, metrics["hits"], metrics["total_questions"])

    # Print comparison table.
    print("\n" + "=" * 55)
    print(f"{'Method':<20} {'Hit-Rate@5':>12} {'Hits':>6} {'Total':>6}")
    print("-" * 55)
    for m in results:
        print(f"{m['method']:<20} {m['hit_rate_at_k']*100:>11.1f}% {m['hits']:>6} {m['total_questions']:>6}")
    print("=" * 55 + "\n")

    return results


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    # By default only run BM25 baseline (no API keys needed).
    # Pass --all to include dense and hybrid+rerank (requires Pinecone + Gemini keys).
    run_all = "--all" in sys.argv
    run_evaluation(
        bm25_only=True,
        dense_only=run_all,
        hybrid_rerank=run_all,
    )
