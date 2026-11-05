"""Refund Service - FastAPI application (Part 1: Setup and Health)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from refund_service.database import init_db, get_db_session
from refund_service.models import Refund, RefundEvent, RefundState, RefundReason
from refund_service.guardrails import RefundStateMachine, RefundGuardrails, TransitionResult, GuardrailCheckResult
from refund_service.schemas import (
    RefundCreate,
    RefundResponse,
    RefundEventResponse,
    RefundActionRequest,
    ErrorResponse,
    HealthResponse,
    RefundState as SchemaRefundState,
    RefundReason as SchemaRefundReason,
)
from refund_service.kafka_producer import get_kafka_producer, kafka_producer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Refund Service database initialized")
    global kafka_producer
    kafka_producer = await get_kafka_producer()
    yield
    if kafka_producer:
        await kafka_producer.stop()


app = FastAPI(
    title="Refund Service",
    description="Food delivery refund management with idempotency and guardrails",
    version="1.0.0",
    lifespan=lifespan,
)


def refund_to_response(refund: Refund) -> RefundResponse:
    return RefundResponse(
        id=refund.id,
        order_id=refund.order_id,
        customer_id=refund.customer_id,
        amount=Decimal(refund.amount),
        currency=refund.currency,
        reason=SchemaRefundReason(refund.reason.value),
        reason_details=refund.reason_details,
        state=SchemaRefundState(refund.state.value),
        requires_approval=refund.requires_approval == "true",
        approved_by=refund.approved_by,
        approved_at=refund.approved_at,
        approval_notes=refund.approval_notes,
        processed_at=refund.processed_at,
        completed_at=refund.completed_at,
        failed_at=refund.failed_at,
        failure_reason=refund.failure_reason,
        created_at=refund.created_at,
        updated_at=refund.updated_at,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@app.post(
    "/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def create_refund(
    refund_data: RefundCreate,
    db: Session = Depends(get_db_session),
):
    """
    Create a new refund request with idempotency and guardrails.
    
    Idempotency: Uses (order_id, idempotency_key) unique constraint.
    Guardrails: Validates amount, time window, duplicates, approval requirements.
    """
    existing = (
        db.query(Refund)
        .filter(Refund.order_id == refund_data.order_id, Refund.idempotency_key == refund_data.idempotency_key)
        .first()
    )
    if existing:
        logger.info(f"Idempotent request for order {refund_data.order_id}, key {refund_data.idempotency_key}")
        return refund_to_response(existing)
    
    guardrails = RefundGuardrails(db)
    
    order_delivered_at = None
    order_total = None
    
    check_result = guardrails.check_refund_request(
        order_id=str(refund_data.order_id),
        amount=str(refund_data.amount),
        reason=refund_data.reason.value,
        order_delivered_at=order_delivered_at,
        order_total=order_total,
    )
    
    if not check_result.passed:
        raise HTTPException(status_code=400, detail=check_result.error)
    
    dup_check = guardrails.check_duplicate_refund(str(refund_data.order_id))
    if not dup_check.passed:
        raise HTTPException(status_code=409, detail=dup_check.error)
    
    refund = Refund(
        order_id=refund_data.order_id,
        customer_id=refund_data.customer_id,
        amount=str(refund_data.amount),
        currency="USD",
        reason=refund_data.reason,
        reason_details=refund_data.reason_details,
        state=RefundState.REQUESTED,
        idempotency_key=refund_data.idempotency_key,
        requires_approval="true" if check_result.requires_approval else "false",
    )
    db.add(refund)
    db.flush()
    
    if kafka_producer:
        await kafka_producer.emit_refund_event(
            refund_id=refund.id,
            event_type="refund.requested",
            from_state=None,
            to_state=RefundState.REQUESTED.value,
            payload={
                "order_id": str(refund.order_id),
                "customer_id": str(refund.customer_id),
                "amount": str(refund.amount),
                "reason": refund.reason.value,
                "requires_approval": refund.requires_approval == "true",
            },
        )
    
    logger.info(f"Created refund {refund.id} for order {refund.order_id}")
    return refund_to_response(refund)


@app.get("/refunds/{refund_id}", response_model=RefundResponse)
async def get_refund(
    refund_id: UUID,
    db: Session = Depends(get_db_session),
):
    refund = db.query(Refund).filter(Refund.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    return refund_to_response(refund)


@app.get("/refunds", response_model=list[RefundResponse])
async def list_refunds(
    customer_id: Optional[UUID] = Query(None),
    order_id: Optional[UUID] = Query(None),
    state: Optional[SchemaRefundState] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    query = db.query(Refund)
    
    if customer_id:
        query = query.filter(Refund.customer_id == customer_id)
    if order_id:
        query = query.filter(Refund.order_id == order_id)
    if state:
        query = query.filter(Refund.state == RefundState(state.value))
    
    refunds = (
        query.order_by(Refund.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    
    return [refund_to_response(r) for r in refunds]


@app.get("/refunds/{refund_id}/events", response_model=list[RefundEventResponse])
async def get_refund_events(
    refund_id: UUID,
    db: Session = Depends(get_db_session),
):
    refund = db.query(Refund).filter(Refund.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    
    events = (
        db.query(RefundEvent)
        .filter(RefundEvent.refund_id == refund_id)
        .order_by(RefundEvent.created_at.asc())
        .all()
    )
    
    return [
        RefundEventResponse(
            id=e.id,
            refund_id=e.refund_id,
            event_type=e.event_type,
            from_state=SchemaRefundState(e.from_state.value) if e.from_state else None,
            to_state=SchemaRefundState(e.to_state.value),
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]


@app.post("/refunds/{refund_id}/action", response_model=RefundResponse)
async def refund_action(
    refund_id: UUID,
    action_request: RefundActionRequest,
    db: Session = Depends(get_db_session),
):
    refund = db.query(Refund).filter(Refund.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    
    sm = RefundStateMachine(db)
    
    if action_request.action == "approve":
        if refund.state != RefundState.REQUESTED:
            raise HTTPException(status_code=400, detail="Can only approve REQUESTED refunds")
        
        result = sm.transition(
            refund,
            RefundState.APPROVED,
            "refund.approved",
            payload=f'{{"approved_by": "{action_request.approved_by}", "notes": "{action_request.notes or ""}"}}',
        )
        
        if result.success:
            refund.approved_by = action_request.approved_by
            refund.approval_notes = action_request.notes
        
    elif action_request.action == "reject":
        if refund.state != RefundState.REQUESTED:
            raise HTTPException(status_code=400, detail="Can only reject REQUESTED refunds")
        
        result = sm.transition(
            refund,
            RefundState.REJECTED,
            "refund.rejected",
            payload=f'{{"rejected_by": "{action_request.approved_by}", "notes": "{action_request.notes or ""}"}}',
        )
        
    elif action_request.action == "process":
        if refund.state != RefundState.APPROVED:
            raise HTTPException(status_code=400, detail="Can only process APPROVED refunds")
        
        result = sm.transition(refund, RefundState.PROCESSING, "refund.processing")
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action_request.action}")
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_refund_event(
            refund_id=refund.id,
            event_type=f"refund.{action_request.action}d",
            from_state=refund.state.value,
            to_state=refund.state.value,
            payload={"action": action_request.action, "notes": action_request.notes},
        )
    
    logger.info(f"Refund {refund_id} action: {action_request.action}")
    return refund_to_response(refund)


@app.post("/refunds/{refund_id}/complete", response_model=RefundResponse)
async def complete_refund(
    refund_id: UUID,
    db: Session = Depends(get_db_session),
):
    refund = db.query(Refund).filter(Refund.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    
    if refund.state != RefundState.PROCESSING:
        raise HTTPException(status_code=400, detail="Can only complete PROCESSING refunds")
    
    sm = RefundStateMachine(db)
    result = sm.transition(refund, RefundState.COMPLETED, "refund.completed")
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_refund_event(
            refund_id=refund.id,
            event_type="refund.completed",
            from_state=RefundState.PROCESSING.value,
            to_state=RefundState.COMPLETED.value,
        )
    
    logger.info(f"Refund {refund_id} completed")
    return refund_to_response(refund)


@app.post("/refunds/{refund_id}/fail", response_model=RefundResponse)
async def fail_refund(
    refund_id: UUID,
    reason: str,
    db: Session = Depends(get_db_session),
):
    refund = db.query(Refund).filter(Refund.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    
    if refund.state not in {RefundState.PROCESSING, RefundState.APPROVED, RefundState.REQUESTED}:
        raise HTTPException(status_code=400, detail="Cannot fail refund in current state")
    
    sm = RefundStateMachine(db)
    result = sm.transition(
        refund,
        RefundState.FAILED,
        "refund.failed",
        payload=f'{{"reason": "{reason}"}}',
    )
    
    if result.success:
        refund.failure_reason = reason
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_refund_event(
            refund_id=refund.id,
            event_type="refund.failed",
            from_state=refund.state.value,
            to_state=RefundState.FAILED.value,
            payload={"reason": reason},
        )
    
    logger.info(f"Refund {refund_id} failed: {reason}")
    return refund_to_response(refund)


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)