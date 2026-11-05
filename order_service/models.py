"""Order service data models and state machine."""

import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()


class OrderState(str, enum.Enum):
    """Order lifecycle states."""
    CREATED = "created"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(Base):
    """Order entity with full lifecycle tracking."""
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    restaurant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    total_amount = Column(String(50), nullable=False)  # Store as string to avoid float precision
    currency = Column(String(3), default="USD")
    state = Column(Enum(OrderState), default=OrderState.CREATED, nullable=False, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=True, index=True)
    shipping_address = Column(Text, nullable=True)
    special_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    events = relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_orders_customer_state", "customer_id", "state"),
        Index("ix_orders_restaurant_state", "restaurant_id", "state"),
    )


class OrderItem(Base):
    """Individual items within an order."""
    __tablename__ = "order_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    quantity = Column(String(10), nullable=False)  # Store as string for precision
    unit_price = Column(String(50), nullable=False)
    total_price = Column(String(50), nullable=False)
    special_requests = Column(Text, nullable=True)
    
    order = relationship("Order", back_populates="items")


class OrderEvent(Base):
    """Event log for order state transitions (audit trail)."""
    __tablename__ = "order_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # state_changed, created, paid, etc.
    from_state = Column(Enum(OrderState), nullable=True)
    to_state = Column(Enum(OrderState), nullable=False)
    payload = Column(Text, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    order = relationship("Order", back_populates="events")
    
    __table_args__ = (
        Index("ix_order_events_order_created", "order_id", "created_at"),
    )


# Valid state transitions
VALID_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.CREATED: {OrderState.PAID, OrderState.CANCELLED},
    OrderState.PAID: {OrderState.PROCESSING, OrderState.CANCELLED},
    OrderState.PROCESSING: {OrderState.SHIPPED, OrderState.CANCELLED},
    OrderState.SHIPPED: {OrderState.DELIVERED, OrderState.CANCELLED},
    OrderState.DELIVERED: {OrderState.REFUNDED},
    OrderState.CANCELLED: set(),  # Terminal state
    OrderState.REFUNDED: set(),   # Terminal state
}

# Terminal states
TERMINAL_STATES = {OrderState.CANCELLED, OrderState.REFUNDED}

# States eligible for refund
REFUND_ELIGIBLE_STATES = {OrderState.DELIVERED}

# States where order can be cancelled
CANCELLABLE_STATES = {OrderState.CREATED, OrderState.PAID, OrderState.PROCESSING}