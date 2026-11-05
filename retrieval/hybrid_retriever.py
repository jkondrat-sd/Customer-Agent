"""Hybrid retriever — dense (Pinecone) + sparse (BM25) search with merge/dedupe.

Architecture rule (skill.md §1): The main retrieval path ALWAYS runs both
dense and sparse searches and merges results before handing off to the
reranker.  Single-method retrieval is only used inside eval baselines.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import TypedDict

from retrieval.utils import tokenize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class RetrievalResult(TypedDict):
    """A single candidate document returned by the retriever."""

    chunk_id: str
    doc_id: str
    text: str
    source: str
    score: float
    method: str  # "dense", "sparse", or "hybrid"


# ---------------------------------------------------------------------------
# Dense search (Pinecone)
# ---------------------------------------------------------------------------

def dense_search(
    query: str,
    *,
    api_key: str,
    index_name: str,
    embedding_api_key: str,
    embedding_model: str,
    top_k: int = 20,
) -> list[RetrievalResult]:
    """Run a dense (semantic) search via Pinecone.

    Embeds *query* with the same model used at ingest time, then queries the
    Pinecone index for the nearest neighbours.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from pinecone import Pinecone

    embedder = GoogleGenerativeAIEmbeddings(
        model=embedding_model,
        google_api_key=embedding_api_key,
    )
    query_vec = embedder.embed_query(query)

    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    response = index.query(vector=query_vec, top_k=top_k, include_metadata=True)

    results: list[RetrievalResult] = []
    for match in response.get("matches", []):
        meta = match.get("metadata", {})
        results.append(
            RetrievalResult(
                chunk_id=meta.get("chunk_id", match["id"]),
                doc_id=meta.get("doc_id", ""),
                text=meta.get("text", ""),
                source=meta.get("source", ""),
                score=float(match["score"]),
                method="dense",
            )
        )
    return results


# ---------------------------------------------------------------------------
# Sparse search (BM25)
# ---------------------------------------------------------------------------

def sparse_search(
    query: str,
    *,
    bm25_index_path: str | Path,
    top_k: int = 20,
) -> list[RetrievalResult]:
    """Run a sparse (lexical) BM25 search over the pickled index.

    Loads the BM25 payload built by ``ingest.build_bm25_index``, scores
    every chunk, and returns the top-k.
    """
    bm25_index_path = Path(bm25_index_path)
    with open(bm25_index_path, "rb") as f:
        payload = pickle.load(f)

    bm25 = payload["bm25"]
    chunk_ids: list[str] = payload["chunk_ids"]
    chunk_texts: list[str] = payload["chunk_texts"]
    chunk_sources: list[str] = payload["chunk_sources"]
    chunk_doc_ids: list[str] = payload["chunk_doc_ids"]

    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)

    # Pair scores with indices and sort descending.
    scored = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    top = scored[:top_k]

    results: list[RetrievalResult] = []
    for idx, score in top:
        if score <= 0:
            continue
        results.append(
            RetrievalResult(
                chunk_id=chunk_ids[idx],
                doc_id=chunk_doc_ids[idx],
                text=chunk_texts[idx],
                source=chunk_sources[idx],
                score=float(score),
                method="sparse",
            )
        )
    return results


# ---------------------------------------------------------------------------
# Merge & dedupe
# ---------------------------------------------------------------------------

def _normalize_scores(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Min-max normalize scores to [0, 1] within a result set."""
    if not results:
        return results
    scores = [r["score"] for r in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        # All scores identical (including single-item sets) → treat as equally best.
        return [{**r, "score": 1.0} for r in results]
    span = hi - lo
    return [
        {**r, "score": (r["score"] - lo) / span}
        for r in results
    ]


def merge_and_dedupe(
    dense_results: list[RetrievalResult],
    sparse_results: list[RetrievalResult],
    *,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> list[RetrievalResult]:
    """Merge dense + sparse results, deduplicate by chunk_id, and sort.

    Scores are normalized to [0, 1] per method, then combined with a
    weighted average.  Duplicates (same chunk_id from both methods) get the
    weighted sum; unique results keep their single-method score.
    """
    # Normalize independently.
    dense_norm = _normalize_scores(dense_results)
    sparse_norm = _normalize_scores(sparse_results)

    merged: dict[str, RetrievalResult] = {}

    for r in dense_norm:
        merged[r["chunk_id"]] = {**r, "score": r["score"] * dense_weight, "method": "hybrid"}

    for r in sparse_norm:
        cid = r["chunk_id"]
        if cid in merged:
            merged[cid]["score"] += r["score"] * sparse_weight
        else:
            merged[cid] = {**r, "score": r["score"] * sparse_weight, "method": "hybrid"}

    combined = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return combined


# ---------------------------------------------------------------------------
# Main hybrid search entry point
# ---------------------------------------------------------------------------

def hybrid_search(
    query: str,
    *,
    top_k: int | None = None,
    pinecone_api_key: str | None = None,
    pinecone_index_name: str | None = None,
    embedding_api_key: str | None = None,
    embedding_model: str | None = None,
    bm25_index_path: str | Path | None = None,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> list[RetrievalResult]:
    """Run hybrid (dense + sparse) retrieval and return merged candidates.

    This is the **only** retrieval function that should be used in the main
    pipeline.  The output must be passed through ``reranker.rerank`` before
    being injected into an LLM prompt (skill.md §2).

    Parameters fall back to ``config.settings`` when ``None``.
    """
    from config import settings

    top_k = top_k or settings.retrieval_top_k
    pinecone_api_key = pinecone_api_key or settings.pinecone_api_key
    pinecone_index_name = pinecone_index_name or settings.pinecone_index_name
    embedding_api_key = embedding_api_key or settings.gemini_api_key
    embedding_model = embedding_model or settings.embedding_model
    bm25_index_path = bm25_index_path or settings.bm25_index_path

    logger.info("Hybrid search: query=%r, top_k=%d", query, top_k)

    # Dense search — gracefully degrade if embedding/Pinecone fails
    dense_results: list[RetrievalResult] = []
    try:
        dense_results = dense_search(
            query,
            api_key=pinecone_api_key,
            index_name=pinecone_index_name,
            embedding_api_key=embedding_api_key,
            embedding_model=embedding_model,
            top_k=top_k,
        )
        logger.info("Dense search returned %d results", len(dense_results))
    except Exception as e:
        logger.warning("Dense search failed (falling back to sparse-only): %s", e)

    # Sparse search — gracefully degrade if BM25 index missing
    sparse_results: list[RetrievalResult] = []
    try:
        sparse_results = sparse_search(
            query,
            bm25_index_path=bm25_index_path,
            top_k=top_k,
        )
        logger.info("Sparse search returned %d results", len(sparse_results))
    except Exception as e:
        logger.warning("Sparse search failed (falling back to dense-only): %s", e)

    merged = merge_and_dedupe(
        dense_results,
        sparse_results,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
    )
    logger.info("Merged candidates: %d", len(merged))
    return merged
