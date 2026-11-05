"""Refund state machine logic with validation and guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta
from decimal import Decimal

from refund_service.models import Refund, RefundState, RefundEvent, REFUND_VALID_TRANSITIONS, REFUND_TERMINAL_STATES, MAX_REFUND_AMOUNT, REFUND_WINDOW_DAYS


class RefundTransitionError(Exception):
    pass


class RefundGuardrailError(Exception):
    pass


class RefundNotFoundError(Exception):
    pass


@dataclass
class TransitionResult:
    success: bool
    refund: Optional[Refund] = None
    error: Optional[str] = None
    event: Optional[RefundEvent] = None


@dataclass
class GuardrailCheckResult:
    passed: bool
    error: Optional[str] = None
    requires_approval: bool = False


class RefundStateMachine:
    def __init__(self, db_session):
        self.db = db_session
    
    def transition(
        self,
        refund: Refund,
        to_state: RefundState,
        event_type: str,
        payload: Optional[str] = None,
    ) -> TransitionResult:
        from_state = refund.state
        
        if to_state not in REFUND_VALID_TRANSITIONS.get(from_state, set()):
            return TransitionResult(
                success=False,
                error=f"Invalid transition from {from_state.value} to {to_state.value}. "
                      f"Valid transitions: {[s.value for s in REFUND_VALID_TRANSITIONS.get(from_state, set())]}",
            )
        
        if from_state in REFUND_TERMINAL_STATES:
            return TransitionResult(
                success=False,
                error=f"Cannot transition from terminal state {from_state.value}",
            )
        
        refund.state = to_state
        refund.updated_at = datetime.utcnow()
        
        if to_state == RefundState.APPROVED:
            refund.approved_at = datetime.utcnow()
        elif to_state == RefundState.PROCESSING:
            refund.processed_at = datetime.utcnow()
        elif to_state == RefundState.COMPLETED:
            refund.completed_at = datetime.utcnow()
        elif to_state == RefundState.FAILED:
            refund.failed_at = datetime.utcnow()
        
        event = RefundEvent(
            refund_id=refund.id,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            payload=payload,
        )
        self.db.add(event)
        self.db.flush()
        
        return TransitionResult(success=True, refund=refund, event=event)
    
    def can_transition(self, from_state: RefundState, to_state: RefundState) -> bool:
        return to_state in REFUND_VALID_TRANSITIONS.get(from_state, set())
    
    def get_valid_transitions(self, from_state: RefundState) -> set[RefundState]:
        return REFUND_VALID_TRANSITIONS.get(from_state, set())
    
    def is_terminal(self, state: RefundState) -> bool:
        return state in REFUND_TERMINAL_STATES


class RefundGuardrails:
    def __init__(self, db_session, order_service_client=None):
        self.db = db_session
        self.order_client = order_service_client
    
    def check_refund_request(
        self,
        order_id: str,
        amount: str,
        reason: str,
        order_delivered_at: Optional[datetime] = None,
        order_total: Optional[str] = None,
    ) -> GuardrailCheckResult:
        if not order_delivered_at:
            return GuardrailCheckResult(
                passed=False,
                error="Order must be delivered before refund can be requested",
            )
        
        days_since_delivery = (datetime.utcnow() - order_delivered_at).days
        if days_since_delivery > REFUND_WINDOW_DAYS:
            return GuardrailCheckResult(
                passed=False,
                error=f"Refund window expired. Must request within {REFUND_WINDOW_DAYS} days of delivery",
            )
        
        if order_total:
            refund_amount = Decimal(amount)
            order_total_decimal = Decimal(order_total)
            if refund_amount > order_total_decimal:
                return GuardrailCheckResult(
                    passed=False,
                    error=f"Refund amount ${amount} exceeds order total ${order_total}",
                )
        
        refund_amount = Decimal(amount)
        max_amount = Decimal(MAX_REFUND_AMOUNT)
        if refund_amount > max_amount:
            return GuardrailCheckResult(
                passed=False,
                error=f"Refund amount ${amount} exceeds maximum allowed ${MAX_REFUND_AMOUNT}",
            )
        
        requires_approval = refund_amount > Decimal("100.00")
        
        return GuardrailCheckResult(
            passed=True,
            requires_approval=requires_approval,
        )
    
    def check_duplicate_refund(self, order_id: str) -> GuardrailCheckResult:
        from refund_service.models import Refund, RefundState
        
        active_states = {RefundState.REQUESTED, RefundState.APPROVED, RefundState.PROCESSING}
        existing = (
            self.db.query(Refund)
            .filter(Refund.order_id == order_id, Refund.state.in_(active_states))
            .first()
        )
        
        if existing:
            return GuardrailCheckResult(
                passed=False,
                error=f"Active refund already exists for this order (refund ID: {existing.id}, state: {existing.state.value})",
            )
        
        return GuardrailCheckResult(passed=True)