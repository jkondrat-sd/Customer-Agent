"""Pydantic schemas for Refund Service API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class RefundState(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RefundReason(str, Enum):
    CUSTOMER_REQUEST = "customer_request"
    DELIVERY_DELAY = "delivery_delay"
    WRONG_ORDER = "wrong_order"
    QUALITY_ISSUE = "quality_issue"
    RESTAURANT_ERROR = "restaurant_error"
    OTHER = "other"


class RefundCreate(BaseModel):
    order_id: UUID
    customer_id: UUID
    amount: Decimal = Field(..., gt=0)
    reason: RefundReason
    reason_details: Optional[str] = None
    idempotency_key: str = Field(..., max_length=255)


class RefundResponse(BaseModel):
    id: UUID
    order_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str
    reason: RefundReason
    reason_details: Optional[str] = None
    state: RefundState
    requires_approval: bool
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RefundEventResponse(BaseModel):
    id: UUID
    refund_id: UUID
    event_type: str
    from_state: Optional[RefundState] = None
    to_state: RefundState
    payload: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class RefundActionRequest(BaseModel):
    action: str  # approve, reject, process
    notes: Optional[str] = None
    approved_by: Optional[UUID] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str = "refund-service"
    version: str = "1.0.0"