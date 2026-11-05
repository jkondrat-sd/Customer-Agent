"""Order state machine logic with validation and transition enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from order_service.models import Order, OrderState, OrderEvent, VALID_TRANSITIONS, TERMINAL_STATES, REFUND_ELIGIBLE_STATES, CANCELLABLE_STATES


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class OrderNotFoundError(Exception):
    """Raised when order is not found."""
    pass


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""
    success: bool
    order: Optional[Order] = None
    error: Optional[str] = None
    event: Optional[OrderEvent] = None


class OrderStateMachine:
    """Enforces valid order state transitions and creates audit events."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def transition(
        self,
        order: Order,
        to_state: OrderState,
        event_type: str,
        payload: Optional[str] = None,
        cancellation_reason: Optional[str] = None,
    ) -> TransitionResult:
        """
        Attempt a state transition with full validation.
        """
        from_state = order.state
        
        # Check if order is in terminal state FIRST
        if from_state in TERMINAL_STATES:
            return TransitionResult(
                success=False,
                error=f"Cannot transition from terminal state {from_state.value}",
            )
        
        # Check if transition is valid
        if to_state not in VALID_TRANSITIONS.get(from_state, set()):
            return TransitionResult(
                success=False,
                error=f"Invalid transition from {from_state.value} to {to_state.value}. "
                      f"Valid transitions: {[s.value for s in VALID_TRANSITIONS.get(from_state, set())]}",
            )
        
        # Special validation for CANCELLED
        if to_state == OrderState.CANCELLED and from_state not in CANCELLABLE_STATES:
            return TransitionResult(
                success=False,
                error=f"Order in {from_state.value} cannot be cancelled",
            )
        
        # Special validation for REFUNDED
        if to_state == OrderState.REFUNDED and from_state not in REFUND_ELIGIBLE_STATES:
            return TransitionResult(
                success=False,
                error=f"Order in {from_state.value} is not eligible for refund",
            )
        
        # Perform the transition
        order.state = to_state
        order.updated_at = datetime.utcnow()
        
        # Update timestamp fields based on target state
        if to_state == OrderState.PAID:
            order.paid_at = datetime.utcnow()
        elif to_state == OrderState.SHIPPED:
            order.shipped_at = datetime.utcnow()
        elif to_state == OrderState.DELIVERED:
            order.delivered_at = datetime.utcnow()
        elif to_state == OrderState.CANCELLED:
            order.cancelled_at = datetime.utcnow()
            order.cancellation_reason = cancellation_reason
        
        # Create audit event
        event = OrderEvent(
            order_id=order.id,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            payload=payload,
        )
        self.db.add(event)
        self.db.flush()
        
        return TransitionResult(success=True, order=order, event=event)
    
    def can_transition(self, from_state: OrderState, to_state: OrderState) -> bool:
        """Check if a transition is valid without performing it."""
        return to_state in VALID_TRANSITIONS.get(from_state, set())
    
    def get_valid_transitions(self, from_state: OrderState) -> set[OrderState]:
        """Get all valid transitions from a given state."""
        return VALID_TRANSITIONS.get(from_state, set())
    
    def is_terminal(self, state: OrderState) -> bool:
        """Check if a state is terminal."""
        return state in TERMINAL_STATES
    
    def is_refund_eligible(self, state: OrderState) -> bool:
        """Check if an order in this state can be refunded."""
        return state in REFUND_ELIGIBLE_STATES
    
    def is_cancellable(self, state: OrderState) -> bool:
        """Check if an order in this state can be cancelled."""
        return state in CANCELLABLE_STATES