"""Refund service data models."""

import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()


class RefundState(str, enum.Enum):
    """Refund lifecycle states."""
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RefundReason(str, enum.Enum):
    """Reasons for refund requests."""
    CUSTOMER_REQUEST = "customer_request"
    DELIVERY_DELAY = "delivery_delay"
    WRONG_ORDER = "wrong_order"
    QUALITY_ISSUE = "quality_issue"
    RESTAURANT_ERROR = "restaurant_error"
    OTHER = "other"


class Refund(Base):
    """Refund entity with full lifecycle tracking."""
    __tablename__ = "refunds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    amount = Column(String(50), nullable=False)  # Store as string to avoid float precision
    currency = Column(String(3), default="USD")
    reason = Column(Enum(RefundReason), nullable=False)
    reason_details = Column(Text, nullable=True)
    state = Column(Enum(RefundState), default=RefundState.REQUESTED, nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    
    # Approval workflow
    requires_approval = Column(String(10), default="false")  # "true" or "false"
    approved_by = Column(UUID(as_uuid=True), nullable=True)  # Human agent ID
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Processing
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="refunds")
    events = relationship("RefundEvent", back_populates="refund", cascade="all, delete-orphan")
    
    __table_args__ = (
        # Idempotency: unique constraint on order_id + idempotency_key
        UniqueConstraint("order_id", "idempotency_key", name="uq_refund_order_idempotency"),
        Index("ix_refunds_customer_state", "customer_id", "state"),
        Index("ix_refunds_order_state", "order_id", "state"),
    )


class RefundEvent(Base):
    """Event log for refund state transitions (audit trail)."""
    __tablename__ = "refund_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refund_id = Column(UUID(as_uuid=True), ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    from_state = Column(Enum(RefundState), nullable=True)
    to_state = Column(Enum(RefundState), nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    refund = relationship("Refund", back_populates="events")
    
    __table_args__ = (
        Index("ix_refund_events_refund_created", "refund_id", "created_at"),
    )


# Valid state transitions for refunds
REFUND_VALID_TRANSITIONS: dict[RefundState, set[RefundState]] = {
    RefundState.REQUESTED: {RefundState.APPROVED, RefundState.REJECTED, RefundState.FAILED},
    RefundState.APPROVED: {RefundState.PROCESSING, RefundState.FAILED},
    RefundState.PROCESSING: {RefundState.COMPLETED, RefundState.FAILED},
    RefundState.COMPLETED: set(),   # Terminal
    RefundState.FAILED: set(),      # Terminal
    RefundState.REJECTED: set(),    # Terminal
}

REFUND_TERMINAL_STATES = {RefundState.COMPLETED, RefundState.FAILED, RefundState.REJECTED}

# Guardrail constants
MAX_REFUND_AMOUNT = "500.00"  # Maximum refund amount
REFUND_WINDOW_DAYS = 30       # Days after delivery to request refund