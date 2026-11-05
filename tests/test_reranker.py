"""Tests for the Cohere API reranker.

Uses unittest.mock to mock the Cohere client to ensure tests run fast and
without network dependency. Tests verify mapping by index, top-n slicing,
and graceful fallback on API failure.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from retrieval.hybrid_retriever import RetrievalResult
from retrieval.reranker import rerank
from cohere.core.api_error import ApiError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_candidates() -> list[RetrievalResult]:
    """Build a set of candidates with known relevance to a test query."""
    return [
        RetrievalResult(
            chunk_id="relevant",
            doc_id="d1",
            text="To reset your password, click Forgot Password on the login page and follow the email instructions.",
            source="password.md",
            score=0.5,
            method="hybrid",
        ),
        RetrievalResult(
            chunk_id="irrelevant_1",
            doc_id="d2",
            text="Our shipping methods include standard, express, and overnight delivery options.",
            source="shipping.md",
            score=0.8,
            method="hybrid",
        ),
        RetrievalResult(
            chunk_id="somewhat_relevant",
            doc_id="d3",
            text="Security features include two-factor authentication, session management, and password policies.",
            source="security.md",
            score=0.6,
            method="hybrid",
        ),
        RetrievalResult(
            chunk_id="irrelevant_2",
            doc_id="d4",
            text="Enterprise billing supports ACH transfers, wire transfers, and purchase orders.",
            source="billing.md",
            score=0.7,
            method="hybrid",
        ),
    ]


@pytest.fixture()
def mock_cohere_client():
    """Mock the Cohere V2 client."""
    with patch("retrieval.reranker.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRerank:
    def test_returns_correct_number(
        self, mock_cohere_client, sample_candidates: list[RetrievalResult]
    ) -> None:
        # Mock response setup
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=0, relevance_score=0.9),
            MagicMock(index=2, relevance_score=0.7),
        ]
        mock_cohere_client.rerank.return_value = mock_response

        results = rerank("How do I reset my password?", sample_candidates, top_n=2)
        assert len(results) == 2
        mock_cohere_client.rerank.assert_called_once()

    def test_mapping_by_index(
        self, mock_cohere_client, sample_candidates: list[RetrievalResult]
    ) -> None:
        mock_response = MagicMock()
        # The mock response returns results out of original order (Cohere sorts by relevance)
        # index 0 is "relevant", index 2 is "somewhat_relevant"
        mock_response.results = [
            MagicMock(index=0, relevance_score=0.99),
            MagicMock(index=2, relevance_score=0.85),
            MagicMock(index=3, relevance_score=0.10),
            MagicMock(index=1, relevance_score=0.05),
        ]
        mock_cohere_client.rerank.return_value = mock_response

        results = rerank("How do I reset my password?", sample_candidates, top_n=4)
        # Verify mapped order
        assert results[0]["chunk_id"] == "relevant"
        assert results[0]["score"] == 0.99
        assert results[1]["chunk_id"] == "somewhat_relevant"
        assert results[1]["score"] == 0.85
        assert results[2]["chunk_id"] == "irrelevant_2"
        assert results[3]["chunk_id"] == "irrelevant_1"

    def test_graceful_degradation_on_api_error(
        self, mock_cohere_client, sample_candidates: list[RetrievalResult]
    ) -> None:
        # Simulate a timeout or rate limit error
        mock_cohere_client.rerank.side_effect = ApiError(body={"message": "Rate limit exceeded"}, status_code=429)

        # Rerank should catch the error and fallback to original candidates
        results = rerank("How do I reset my password?", sample_candidates, top_n=2)
        
        # It should return the top 2 from the original list
        assert len(results) == 2
        assert results[0]["chunk_id"] == "relevant"
        assert results[1]["chunk_id"] == "irrelevant_1"

    def test_empty_candidates(self) -> None:
        results = rerank("anything", [], top_n=5)
        assert results == []

    def test_top_n_larger_than_candidates(
        self, mock_cohere_client, sample_candidates: list[RetrievalResult]
    ) -> None:
        mock_response = MagicMock()
        # Returns all 4
        mock_response.results = [
            MagicMock(index=0, relevance_score=0.99),
            MagicMock(index=1, relevance_score=0.85),
            MagicMock(index=2, relevance_score=0.10),
            MagicMock(index=3, relevance_score=0.05),
        ]
        mock_cohere_client.rerank.return_value = mock_response

        results = rerank("query", sample_candidates, top_n=100)
        assert len(results) == len(sample_candidates)
