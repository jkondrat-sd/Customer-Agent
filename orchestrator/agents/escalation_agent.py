"""Escalation agent — human handoff with database logging.

Architecture rules (skill.md):
- §4: Every agent response carries a confidence score.
- §6: All conversation state and eval-relevant data goes to PostgreSQL.
"""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from db.models import Conversation, Escalation, Message
from orchestrator.state import SupportState

logger = logging.getLogger(__name__)

# Lazy DB engine — created on first use to avoid crashing at import time
_engine = None
_SessionLocal = None

def _get_db():
    """Return a session factory, creating the engine on first call."""
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = create_engine(config.settings.database_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _SessionLocal


def escalation_agent_node(state: SupportState) -> SupportState:
    """Escalation agent — logs an escalation record and returns a handoff message.

    Creates Conversation + Escalation records in PostgreSQL (skill.md §6).
    Reports confidence = 1.0 because escalation is a definitive routing decision.
    """
    messages = state.get("messages", [])

    # Extract the user's original message for context
    user_query = ""
    if messages:
        last_msg = messages[-1]
        user_query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    # Determine escalation reason from context
    confidence = state.get("confidence", 0.0)
    retry_count = state.get("retry_count", 0)

    if retry_count >= 2:
        reason = (
            f"Self-correction loop exhausted after {retry_count} retries "
            f"(confidence={confidence:.2f}). Original query: {user_query}"
        )
    else:
        reason = f"Intent classified as complex — requires human intervention. Query: {user_query}"

    # Log to PostgreSQL (skill.md §6)
    try:
        with _get_db()() as db:
            conversation = Conversation()
            db.add(conversation)
            db.flush()

            # Log the user's message
            user_msg = Message(
                conversation_id=conversation.id,
                role="human",
                content=user_query,
            )
            db.add(user_msg)

            # Log the escalation
            escalation = Escalation(
                conversation_id=conversation.id,
                reason=reason,
            )
            db.add(escalation)

            # Log the AI response
            handoff_text = (
                "I understand your concern and want to make sure you get the best help possible. "
                "I'm connecting you with a human support specialist who can assist you directly.\n\n"
                "📋 **Your case has been logged** and a support agent will be with you shortly.\n"
                "📧 You can also reach us at **support@flowdesk.com** or call **1-800-FLOWDESK**."
            )
            ai_msg = Message(
                conversation_id=conversation.id,
                role="ai",
                content=handoff_text,
            )
            db.add(ai_msg)
            db.commit()

            logger.info(
                "Escalation logged: conversation_id=%s, reason=%s",
                conversation.id,
                reason,
            )
    except Exception as e:
        logger.error("Failed to log escalation to database: %s", e)
        handoff_text = (
            "I'm connecting you with a human support specialist. "
            "Please hold while we transfer your case."
        )

    return {
        "messages": [AIMessage(content=handoff_text)],
        "confidence": 1.0,  # Escalation is a definitive decision
    }
