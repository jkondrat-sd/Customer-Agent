"""Order Service - FastAPI application."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, select

from order_service.database import init_db, get_db_session, get_db
from order_service.models import Order, OrderItem, OrderState, OrderEvent
from order_service.state_machine import OrderStateMachine, StateTransitionError
from order_service.schemas import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
    OrderEventResponse,
    OrderActionRequest,
    OrderItemResponse,
    ErrorResponse,
    HealthResponse,
    OrderState as SchemaOrderState,
)
from order_service.kafka_producer import get_kafka_producer, kafka_producer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    init_db()
    logger.info("Order Service database initialized")
    global kafka_producer
    kafka_producer = await get_kafka_producer()
    yield
    if kafka_producer:
        await kafka_producer.stop()


app = FastAPI(
    title="Order Service",
    description="Food delivery order management with state machine",
    version="1.0.0",
    lifespan=lifespan,
)


def order_to_response(order: Order) -> OrderResponse:
    """Convert Order model to response schema."""
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        restaurant_id=order.restaurant_id,
        total_amount=Decimal(order.total_amount),
        currency=order.currency,
        state=SchemaOrderState(order.state.value),
        shipping_address=order.shipping_address,
        special_instructions=order.special_instructions,
        items=[
            OrderItemResponse(
                id=item.id,
                menu_item_id=item.menu_item_id,
                name=item.name,
                quantity=int(item.quantity),
                unit_price=Decimal(item.unit_price),
                total_price=Decimal(item.total_price),
                special_requests=item.special_requests,
            )
            for item in order.items
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
        paid_at=order.paid_at,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        cancelled_at=order.cancelled_at,
        cancellation_reason=order.cancellation_reason,
    )


def calculate_total(items: List) -> Decimal:
    """Calculate order total from items."""
    return sum(Decimal(item.unit_price) * item.quantity for item in items)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db_session),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Create a new order with idempotency support.
    
    Use Idempotency-Key header to safely retry requests.
    """
    key = idempotency_key or order_data.idempotency_key
    if key:
        existing = db.query(Order).filter(Order.idempotency_key == key).first()
        if existing:
            logger.info(f"Idempotent request for key {key}, returning existing order {existing.id}")
            return order_to_response(existing)
    
    total = calculate_total(order_data.items)
    
    order = Order(
        customer_id=order_data.customer_id,
        restaurant_id=order_data.restaurant_id,
        total_amount=str(total),
        currency="USD",
        state=OrderState.CREATED,
        idempotency_key=key,
        shipping_address=order_data.shipping_address,
        special_instructions=order_data.special_instructions,
    )
    db.add(order)
    db.flush()
    
    for item_data in order_data.items:
        item_total = Decimal(item_data.unit_price) * item_data.quantity
        item = OrderItem(
            order_id=order.id,
            menu_item_id=item_data.menu_item_id,
            name=item_data.name,
            quantity=str(item_data.quantity),
            unit_price=str(item_data.unit_price),
            total_price=str(item_total),
            special_requests=item_data.special_requests,
        )
        db.add(item)
    
    db.flush()
    
    if kafka_producer:
        items_payload = [
            {
                "menu_item_id": str(item.menu_item_id),
                "name": item.name,
                "quantity": int(item.quantity),
                "unit_price": str(item.unit_price),
                "total_price": str(item.total_price),
            }
            for item in order.items
        ]
        await kafka_producer.emit_order_created(
            order_id=order.id,
            customer_id=order.customer_id,
            restaurant_id=order.restaurant_id,
            total_amount=str(total),
            items=items_payload,
        )
    
    logger.info(f"Created order {order.id} for customer {order.customer_id}")
    return order_to_response(order)


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Get order by ID with all items."""
    order = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_to_response(order)


@app.get("/orders", response_model=OrderListResponse)
async def list_orders(
    customer_id: Optional[UUID] = Query(None),
    restaurant_id: Optional[UUID] = Query(None),
    state: Optional[SchemaOrderState] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """List orders with optional filters."""
    query = db.query(Order).options(joinedload(Order.items))
    
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    if restaurant_id:
        query = query.filter(Order.restaurant_id == restaurant_id)
    if state:
        query = query.filter(Order.state == OrderState(state.value))
    
    total = query.count()
    
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    
    return OrderListResponse(
        orders=[order_to_response(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/orders/{order_id}/events", response_model=List[OrderEventResponse])
async def get_order_events(
    order_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Get all events for an order (audit trail)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    events = (
        db.query(OrderEvent)
        .filter(OrderEvent.order_id == order_id)
        .order_by(OrderEvent.created_at.asc())
        .all()
    )
    
    return [
        OrderEventResponse(
            id=e.id,
            order_id=e.order_id,
            event_type=e.event_type,
            from_state=SchemaOrderState(e.from_state.value) if e.from_state else None,
            to_state=SchemaOrderState(e.to_state.value),
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]


@app.post("/orders/{order_id}/pay", response_model=OrderResponse)
async def pay_order(
    order_id: UUID,
    db: Session = Depends(get_db_session),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Mark order as paid."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    sm = OrderStateMachine(db)
    result = sm.transition(order, OrderState.PAID, "order.paid")
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_state_changed(
            order_id=order.id,
            from_state=OrderState.CREATED.value,
            to_state=OrderState.PAID.value,
        )
    
    logger.info(f"Order {order_id} paid")
    return order_to_response(order)


@app.post("/orders/{order_id}/process", response_model=OrderResponse)
async def process_order(
    order_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Move order to processing (restaurant preparing)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    sm = OrderStateMachine(db)
    result = sm.transition(order, OrderState.PROCESSING, "order.processing")
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_state_changed(
            order_id=order.id,
            from_state=OrderState.PAID.value,
            to_state=OrderState.PROCESSING.value,
        )
    
    logger.info(f"Order {order_id} processing")
    return order_to_response(order)


@app.post("/orders/{order_id}/ship", response_model=OrderResponse)
async def ship_order(
    order_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Mark order as shipped (handed to delivery)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    sm = OrderStateMachine(db)
    result = sm.transition(order, OrderState.SHIPPED, "order.shipped")
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_state_changed(
            order_id=order.id,
            from_state=OrderState.PROCESSING.value,
            to_state=OrderState.SHIPPED.value,
        )
    
    logger.info(f"Order {order_id} shipped")
    return order_to_response(order)


@app.post("/orders/{order_id}/deliver", response_model=OrderResponse)
async def deliver_order(
    order_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Mark order as delivered."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    sm = OrderStateMachine(db)
    result = sm.transition(order, OrderState.DELIVERED, "order.delivered")
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_state_changed(
            order_id=order.id,
            from_state=OrderState.SHIPPED.value,
            to_state=OrderState.DELIVERED.value,
        )
    
    logger.info(f"Order {order_id} delivered")
    return order_to_response(order)


@app.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID,
    request: OrderActionRequest,
    db: Session = Depends(get_db_session),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Cancel an order (only from cancellable states)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    sm = OrderStateMachine(db)
    result = sm.transition(
        order,
        OrderState.CANCELLED,
        "order.cancelled",
        cancellation_reason=request.reason,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    if kafka_producer:
        await kafka_producer.emit_state_changed(
            order_id=order.id,
            from_state=order.state.value,
            to_state=OrderState.CANCELLED.value,
            reason=request.reason,
        )
    
    logger.info(f"Order {order_id} cancelled: {request.reason}")
    return order_to_response(order)


@app.exception_handler(StateTransitionError)
async def state_transition_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid state transition", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)