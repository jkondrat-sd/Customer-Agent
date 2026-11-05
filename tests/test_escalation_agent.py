"""Tests for the escalation agent.

Validates that the escalation agent:
- Logs escalation records to the database (skill.md §6)
- Returns proper confidence score of 1.0 (skill.md §4)
- Provides a professional handoff message
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from orchestrator.agents.escalation_agent import escalation_agent_node
from orchestrator.state import SupportState


def _mock_get_db():
    """Helper: return a mock _get_db that yields a mock session."""
    mock_db = MagicMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)
    return mock_session_factory, mock_db


@patch("orchestrator.agents.escalation_agent._get_db")
def test_escalation_agent_logs_to_db(mock_get_db):
    """Escalation agent creates Conversation + Escalation records in the DB."""
    mock_session_factory, mock_db = _mock_get_db()
    mock_get_db.return_value = mock_session_factory

    state: SupportState = {
        "messages": [HumanMessage(content="I'm very frustrated with your service!")],
        "intent": "complex",
        "retrieved_context": [],
        "confidence": 0.0,
        "retry_count": 0,
    }

    _result = escalation_agent_node(state)

    # Should have added Conversation, user Message, Escalation, and AI Message
    assert mock_db.add.call_count == 4
    assert mock_db.commit.called


@patch("orchestrator.agents.escalation_agent._get_db")
def test_escalation_agent_confidence_is_one(mock_get_db):
    """Escalation is a definitive decision — confidence must be 1.0."""
    mock_session_factory, mock_db = _mock_get_db()
    mock_get_db.return_value = mock_session_factory

    state: SupportState = {
        "messages": [HumanMessage(content="Let me speak to a manager")],
        "intent": "complex",
        "retrieved_context": [],
        "confidence": 0.0,
        "retry_count": 0,
    }

    result = escalation_agent_node(state)

    assert result["confidence"] == 1.0


@patch("orchestrator.agents.escalation_agent._get_db")
def test_escalation_agent_returns_handoff_message(mock_get_db):
    """Escalation agent returns a professional handoff message."""
    mock_session_factory, mock_db = _mock_get_db()
    mock_get_db.return_value = mock_session_factory

    state: SupportState = {
        "messages": [HumanMessage(content="This is unacceptable!")],
        "intent": "complex",
        "retrieved_context": [],
        "confidence": 0.0,
        "retry_count": 0,
    }

    result = escalation_agent_node(state)

    message = result["messages"][0].content
    assert "support" in message.lower() or "specialist" in message.lower()
    assert "flowdesk" in message.lower()


@patch("orchestrator.agents.escalation_agent._get_db")
def test_escalation_after_retries(mock_get_db):
    """Escalation triggered after self-correction loop exhaustion includes retry info."""
    mock_session_factory, mock_db = _mock_get_db()
    mock_get_db.return_value = mock_session_factory

    state: SupportState = {
        "messages": [HumanMessage(content="What is X?")],
        "intent": "complex",
        "retrieved_context": ["some context"],
        "confidence": 0.3,
        "retry_count": 2,
    }

    result = escalation_agent_node(state)

    assert result["confidence"] == 1.0
    assert len(result["messages"]) == 1


@patch("orchestrator.agents.escalation_agent._get_db")
def test_escalation_db_failure_graceful(mock_get_db):
    """Escalation agent handles DB failures gracefully."""
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(
        side_effect=Exception("DB connection refused")
    )
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_db.return_value = mock_session_factory

    state: SupportState = {
        "messages": [HumanMessage(content="Help me!")],
        "intent": "complex",
        "retrieved_context": [],
        "confidence": 0.0,
        "retry_count": 0,
    }

    result = escalation_agent_node(state)

    # Should still return a handoff message, not crash
    assert result["confidence"] == 1.0
    assert len(result["messages"]) == 1
