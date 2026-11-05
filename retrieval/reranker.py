"""Cohere API reranker for hybrid retrieval candidates.

Architecture rule (skill.md §2): Reranking is **mandatory** before context
injection — raw hybrid-merged candidates never go straight into an LLM
prompt. This module scores each (query, candidate_text) pair through
Cohere's rerank-v3.5 API and returns the top-n.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from retrieval.hybrid_retriever import RetrievalResult

from functools import cache
import cohere
from cohere.core.api_error import ApiError

logger = logging.getLogger(__name__)

_MODEL_NAME = "rerank-v3.5"


@cache
def get_client() -> cohere.ClientV2:
    """Lazy-load the Cohere client to avoid initializing if not needed."""
    from config import settings
    # Initialize with an explicit timeout to prevent hanging the event loop.
    return cohere.ClientV2(api_key=settings.cohere_api_key, timeout=5.0)


def rerank(
    query: str,
    candidates: list["RetrievalResult"],
    *,
    top_n: int | None = None,
) -> list["RetrievalResult"]:
    """Score and re-order *candidates* against *query*, return top-n.

    Each candidate's ``score`` field is **replaced** with the Cohere API
    score so downstream consumers see the reranked score, not the raw
    retrieval score.

    If the Cohere API fails (timeout, rate limit, etc.), this function degrades
    gracefully by returning the top_n original candidates without reranking,
    allowing the downstream generation to proceed.

    Parameters
    ----------
    query : str
        The user's search query.
    candidates : list[RetrievalResult]
        Merged hybrid candidates from ``hybrid_retriever.merge_and_dedupe``.
    top_n : int | None
        Number of results to return. Falls back to ``config.settings.rerank_top_n``.
    """
    if top_n is None:
        from config import settings
        top_n = settings.rerank_top_n

    if not candidates:
        return []

    client = get_client()
    docs = [c["text"] for c in candidates]

    try:
        logger.info(f"Calling Cohere Rerank API ({_MODEL_NAME}) for {len(docs)} documents.")
        response = client.rerank(
            model=_MODEL_NAME,
            query=query,
            documents=docs,
            top_n=top_n,
        )
    except (ApiError, Exception) as e:
        logger.warning(
            f"Cohere Rerank API failed ({type(e).__name__}: {e}). "
            f"Falling back to original retrieval order."
        )
        # Graceful degradation: return original order truncated to top_n
        return candidates[:top_n]

    # Map the response scores back to the original candidates using response.results[i].index
    top: list["RetrievalResult"] = []
    for result in response.results:
        original_candidate = candidates[result.index]
        # Attach the new score
        top.append({**original_candidate, "score": float(result.relevance_score)})

    if top:
        logger.info(
            "Reranked %d candidates → top %d (score range: %.4f – %.4f)",
            len(candidates),
            len(top),
            top[-1]["score"],
            top[0]["score"],
        )
    return top
