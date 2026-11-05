"""Tests for Order Service state machine."""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from order_service.models import Order, OrderState, OrderEvent, VALID_TRANSITIONS, TERMINAL_STATES
from order_service.state_machine import OrderStateMachine, StateTransitionError


class TestOrderStateMachine:
    """Test the order state machine transitions."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)
    
    @pytest.fixture
    def state_machine(self, mock_db):
        return OrderStateMachine(mock_db)
    
    @pytest.fixture
    def sample_order(self):
        order = Order(
            id=uuid4(),
            customer_id=uuid4(),
            restaurant_id=uuid4(),
            total_amount="25.00",
            currency="USD",
            state=OrderState.CREATED,
        )
        return order
    
    def test_valid_transition_created_to_paid(self, state_machine, sample_order):
        result = state_machine.transition(sample_order, OrderState.PAID, "order.paid")
        assert result.success is True
        assert result.order.state == OrderState.PAID
    
    def test_valid_transition_paid_to_processing(self, state_machine, sample_order):
        sample_order.state = OrderState.PAID
        result = state_machine.transition(sample_order, OrderState.PROCESSING, "order.processing")
        assert result.success is True
        assert result.order.state == OrderState.PROCESSING
    
    def test_valid_transition_processing_to_shipped(self, state_machine, sample_order):
        sample_order.state = OrderState.PROCESSING
        result = state_machine.transition(sample_order, OrderState.SHIPPED, "order.shipped")
        assert result.success is True
        assert result.order.state == OrderState.SHIPPED
    
    def test_valid_transition_shipped_to_delivered(self, state_machine, sample_order):
        sample_order.state = OrderState.SHIPPED
        result = state_machine.transition(sample_order, OrderState.DELIVERED, "order.delivered")
        assert result.success is True
        assert result.order.state == OrderState.DELIVERED

    def test_invalid_transition_created_to_shipped(self, state_machine, sample_order):
        result = state_machine.transition(sample_order, OrderState.SHIPPED, "order.shipped")
        assert result.success is False
        assert "Invalid transition" in result.error
        assert sample_order.state == OrderState.CREATED

    def test_invalid_transition_delivered_to_processing(self, state_machine, sample_order):
        sample_order.state = OrderState.DELIVERED
        result = state_machine.transition(sample_order, OrderState.PROCESSING, "order.processing")
        assert result.success is False
        assert "Invalid transition" in result.error

    def test_terminal_state_cancelled_no_transitions(self, state_machine, sample_order):
        sample_order.state = OrderState.CANCELLED
        result = state_machine.transition(sample_order, OrderState.PAID, "order.paid")
        assert result.success is False
        assert "terminal state" in result.error

    def test_terminal_state_refunded_no_transitions(self, state_machine, sample_order):
        sample_order.state = OrderState.REFUNDED
        result = state_machine.transition(sample_order, OrderState.CANCELLED, "order.cancelled")
        assert result.success is False
        assert "terminal state" in result.error

    def test_cancel_from_created(self, state_machine, sample_order):
        result = state_machine.transition(
            sample_order, OrderState.CANCELLED, "order.cancelled",
            cancellation_reason="Customer requested"
        )
        assert result.success is True
        assert result.order.state == OrderState.CANCELLED
        assert result.order.cancellation_reason == "Customer requested"

    def test_cancel_from_paid(self, state_machine, sample_order):
        sample_order.state = OrderState.PAID
        result = state_machine.transition(sample_order, OrderState.CANCELLED, "order.cancelled")
        assert result.success is True
        assert result.order.state == OrderState.CANCELLED

    def test_cancel_from_shipped_fails(self, state_machine, sample_order):
        sample_order.state = OrderState.SHIPPED
        result = state_machine.transition(sample_order, OrderState.CANCELLED, "order.cancelled")
        assert result.success is False
        assert "cannot be cancelled" in result.error

    def test_refund_from_delivered(self, state_machine, sample_order):
        sample_order.state = OrderState.DELIVERED
        result = state_machine.transition(sample_order, OrderState.REFUNDED, "order.refunded")
        assert result.success is True
        assert result.order.state == OrderState.REFUNDED

    def test_refund_from_paid_fails(self, state_machine, sample_order):
        sample_order.state = OrderState.PAID
        result = state_machine.transition(sample_order, OrderState.REFUNDED, "order.refunded")
        assert result.success is False
        assert "Invalid transition" in result.error

    def test_can_transition_helper(self, state_machine):
        assert state_machine.can_transition(OrderState.CREATED, OrderState.PAID) is True
        assert state_machine.can_transition(OrderState.CREATED, OrderState.SHIPPED) is False
        assert state_machine.can_transition(OrderState.DELIVERED, OrderState.REFUNDED) is True
        assert state_machine.can_transition(OrderState.CANCELLED, OrderState.PAID) is False

    def test_get_valid_transitions(self, state_machine):
        transitions = state_machine.get_valid_transitions(OrderState.CREATED)
        assert OrderState.PAID in transitions
        assert OrderState.CANCELLED in transitions
        assert OrderState.SHIPPED not in transitions

    def test_is_terminal(self, state_machine):
        assert state_machine.is_terminal(OrderState.CANCELLED) is True
        assert state_machine.is_terminal(OrderState.REFUNDED) is True
        assert state_machine.is_terminal(OrderState.DELIVERED) is False
        assert state_machine.is_terminal(OrderState.CREATED) is False
        assert state_machine.is_terminal(OrderState.PAID) is False

    def test_is_refund_eligible(self, state_machine):
        assert state_machine.is_refund_eligible(OrderState.DELIVERED) is True
        assert state_machine.is_refund_eligible(OrderState.PAID) is False
        assert state_machine.is_refund_eligible(OrderState.CANCELLED) is False

    def test_is_cancellable(self, state_machine):
        assert state_machine.is_cancellable(OrderState.CREATED) is True
        assert state_machine.is_cancellable(OrderState.PAID) is True
        assert state_machine.is_cancellable(OrderState.PROCESSING) is True
        assert state_machine.is_cancellable(OrderState.SHIPPED) is False
        assert state_machine.is_cancellable(OrderState.DELIVERED) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])