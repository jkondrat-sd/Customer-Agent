"""Pydantic schemas for Order Service API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class OrderState(str, Enum):
    """Order lifecycle states (matches DB enum)."""
    CREATED = "created"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderItemCreate(BaseModel):
    """Input for creating an order item."""
    menu_item_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., ge=0)
    special_requests: Optional[str] = None


class OrderItemResponse(BaseModel):
    """Order item in responses."""
    id: UUID
    menu_item_id: UUID
    name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    special_requests: Optional[str] = None
    
    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    """Input for creating a new order."""
    customer_id: UUID
    restaurant_id: UUID
    items: List[OrderItemCreate] = Field(..., min_length=1)
    shipping_address: Optional[str] = None
    special_instructions: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=255)
    
    @field_validator("items")
    @classmethod
    def validate_items(cls, v):
        if not v:
            raise ValueError("At least one item is required")
        return v


class OrderUpdate(BaseModel):
    """Input for updating an order (limited fields)."""
    shipping_address: Optional[str] = None
    special_instructions: Optional[str] = None


class OrderResponse(BaseModel):
    """Full order response."""
    id: UUID
    customer_id: UUID
    restaurant_id: UUID
    total_amount: Decimal
    currency: str
    state: OrderState
    shipping_address: Optional[str] = None
    special_instructions: Optional[str] = None
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    
    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    """Paginated order list response."""
    orders: List[OrderResponse]
    total: int
    page: int
    page_size: int


class OrderEventResponse(BaseModel):
    """Order event in responses."""
    id: UUID
    order_id: UUID
    event_type: str
    from_state: Optional[OrderState] = None
    to_state: OrderState
    payload: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class OrderActionRequest(BaseModel):
    """Request for order actions (cancel, etc.)."""
    reason: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=255)


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str = "order-service"
    version: str = "1.0.0"