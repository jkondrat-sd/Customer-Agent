import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="conversation")
    escalations = relationship("Escalation", back_populates="conversation")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(Uuid, ForeignKey('conversations.id'))
    role = Column(String(50))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")
    retrieval_logs = relationship("RetrievalLog", back_populates="message")
    confidence_scores = relationship("ConfidenceScore", back_populates="message")

class RetrievalLog(Base):
    __tablename__ = 'retrieval_logs'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id = Column(Uuid, ForeignKey('messages.id'))
    query = Column(Text)
    retrieved_chunks = Column(JSON)
    rerank_scores = Column(JSON)
    
    message = relationship("Message", back_populates="retrieval_logs")

class ConfidenceScore(Base):
    __tablename__ = 'confidence_scores'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id = Column(Uuid, ForeignKey('messages.id'))
    retrieval_score = Column(Float)
    llm_confidence = Column(Float)
    groundedness = Column(Float)
    final_score = Column(Float)
    
    message = relationship("Message", back_populates="confidence_scores")

class Escalation(Base):
    __tablename__ = 'escalations'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(Uuid, ForeignKey('conversations.id'))
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="escalations")

class Feedback(Base):
    """User feedback (thumbs up/down) on agent responses (build_guide stretch goal)."""
    __tablename__ = 'feedback'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), nullable=True)
    message_content = Column(Text)
    response_content = Column(Text)
    rating = Column(String(10))  # "up" or "down"
    created_at = Column(DateTime, default=datetime.utcnow)

