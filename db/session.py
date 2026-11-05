"""Database session management and telemetry logging.

Centralizes the lazy-loaded SQLAlchemy engine and session factory to avoid
duplication across agents and API endpoints. Provides helper functions for
logging telemetry (messages, confidence scores, feedback).
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from db.models import Message, ConfidenceScore, RetrievalLog, Feedback

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None

def get_db():
    """Return a thread-safe session factory, creating the engine on first call."""
    global _engine, _SessionLocal
    if _SessionLocal is None:
        # Added pool_pre_ping=True to handle stale connections in Serverless environments
        _engine = create_engine(config.settings.database_url, pool_pre_ping=True, pool_recycle=300)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _SessionLocal

def log_telemetry(
    answer: str,
    query: str | None = None,
    llm_confidence: float = 0.0,
    retrieval_score: float = 1.0,
    final_confidence: float = 0.0,
    retrieved_chunks: list[str] | None = None,
    rerank_scores: list[float] | None = None,
) -> None:
    """Log an interaction and its confidence scores to the database."""
    try:
        with get_db()() as db:
            log_msg = Message(role="ai", content=answer)
            db.add(log_msg)
            db.flush()

            # Log retrieval details if provided (mostly for RAG)
            if query and retrieved_chunks is not None:
                retrieval_log = RetrievalLog(
                    message_id=log_msg.id,
                    query=query,
                    retrieved_chunks=retrieved_chunks,
                    rerank_scores=rerank_scores or []
                )
                db.add(retrieval_log)

            conf_score = ConfidenceScore(
                message_id=log_msg.id,
                retrieval_score=retrieval_score,
                llm_confidence=llm_confidence,
                groundedness=final_confidence,  # Rough proxy
                final_score=final_confidence
            )
            
            db.add(conf_score)
            db.commit()
    except Exception as e:
        logger.error("Failed to log telemetry: %s", e)

def log_feedback(
    rating: str,
    response_content: str,
    message_content: str = "",
    conversation_id: str | None = None,
) -> str | None:
    """Record user feedback (thumbs up/down) on an agent response."""
    try:
        with get_db()() as db:
            feedback = Feedback(
                conversation_id=conversation_id,
                message_content=message_content,
                response_content=response_content,
                rating=rating,
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            logger.info("Feedback recorded: rating=%s", rating)
            return str(feedback.id)
    except Exception as e:
        logger.error("Failed to record feedback: %s", e)
        return None
