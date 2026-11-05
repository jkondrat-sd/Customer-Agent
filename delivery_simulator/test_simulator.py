"""Tests for Delivery Simulator."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from delivery_simulator.main import DeliverySimulator, DELAY_PROBABILITY, DELAY_MIN_MINUTES, DELAY_MAX_MINUTES


class TestDeliverySimulator:
    """Test the delivery simulator logic."""
    
    @pytest.fixture
    def simulator(self):
        sim = DeliverySimulator()
        return sim
    
    def test_delay_probability_range(self):
        """Test that delay probability is valid."""
        assert 0.0 <= DELAY_PROBABILITY <= 1.0
    
    def test_delay_minutes_range(self):
        """Test that delay minutes range is valid."""
        assert DELAY_MIN_MINUTES > 0
        assert DELAY_MAX_MINUTES > DELAY_MIN_MINUTES
    
    def test_process_order_event_not_shipped(self, simulator):
        """Test that non-shipped events are ignored."""
        event = {
            "event_type": "order.state_changed",
            "order_id": "test-order-123",
            "to_state": "paid",
        }
        mock_producer = MagicMock()
        simulator.producer = mock_producer
        import asyncio
        asyncio.run(simulator._process_order_event(event))
        mock_producer.send_and_wait.assert_not_called()
    
    def test_process_order_event_shipped(self, simulator):
        """Test that shipped events trigger delivery simulation."""
        event = {
            "event_type": "order.state_changed",
            "order_id": "test-order-123",
            "to_state": "shipped",
        }
        mock_producer = AsyncMock()
        simulator.producer = mock_producer
        import asyncio
        with patch("delivery_simulator.main.asyncio.sleep", new=AsyncMock()):
            asyncio.run(simulator._process_order_event(event))
        assert mock_producer.send_and_wait.call_count >= 2

    def test_emit_delivery_event_structure(self, simulator):
        """Test delivery event structure."""
        mock_producer = AsyncMock()
        simulator.producer = mock_producer
        import asyncio
        asyncio.run(simulator._emit_delivery_event(
            order_id="test-123",
            status="delivered",
            event_type="delivery.delivered",
        ))
        mock_producer.send_and_wait.assert_called_once()
        call_args = mock_producer.send_and_wait.call_args
        assert call_args[0][0] == "delivery.events"
        assert call_args[1]["key"] == "test-123"
        event_data = call_args[1]["value"]
        if isinstance(event_data, str):
            event_data = json.loads(event_data)
        assert event_data["order_id"] == "test-123"
        assert event_data["status"] == "delivered"
        assert event_data["event_type"] == "delivery.delivered"
        assert event_data["service"] == "delivery-simulator"

    def test_emit_delayed_event_structure(self, simulator):
        """Test delayed event includes delay info."""
        mock_producer = AsyncMock()
        simulator.producer = mock_producer
        import asyncio
        asyncio.run(simulator._emit_delivery_event(
            order_id="test-456",
            status="delayed",
            event_type="delivery.delayed",
            delay_minutes=30,
            reason="weather_conditions",
        ))
        mock_producer.send_and_wait.assert_called_once()
        call_args = mock_producer.send_and_wait.call_args
        event_data = call_args[1]["value"]
        if isinstance(event_data, str):
            event_data = json.loads(event_data)
        assert event_data["delay_minutes"] == 30
        assert event_data["reason"] == "weather_conditions"
        assert event_data["status"] == "delayed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])