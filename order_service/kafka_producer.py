"""Kafka producer for order service events."""

import json
import logging
from typing import Optional
from datetime import datetime
from uuid import UUID

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


class OrderKafkaProducer:
    """Async Kafka producer for order events."""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer: Optional[AIOKafkaProducer] = None
        self.topic = "order.events"
    
    async def start(self) -> None:
        """Start the Kafka producer."""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await self.producer.start()
        logger.info("Order Kafka producer started")
    
    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Order Kafka producer stopped")
    
    async def emit_order_event(
        self,
        order_id: UUID,
        event_type: str,
        from_state: Optional[str],
        to_state: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Emit an order event to Kafka."""
        if not self.producer:
            logger.warning("Kafka producer not started, skipping event emission")
            return
        
        event = {
            "event_id": str(UUID(int=0)),  # Will be replaced by consumer
            "order_id": str(order_id),
            "event_type": event_type,
            "from_state": from_state,
            "to_state": to_state,
            "payload": payload or {},
            "timestamp": datetime.utcnow().isoformat(),
            "service": "order-service",
        }
        
        try:
            await self.producer.send_and_wait(
                self.topic,
                key=str(order_id),
                value=event,
            )
            logger.debug(f"Emitted order event: {event_type} for order {order_id}")
        except KafkaError as e:
            logger.error(f"Failed to emit order event: {e}")
            # Don't raise - event emission failure shouldn't break the transaction
    
    async def emit_order_created(
        self,
        order_id: UUID,
        customer_id: UUID,
        restaurant_id: UUID,
        total_amount: str,
        items: list,
    ) -> None:
        """Emit order.created event."""
        await self.emit_order_event(
            order_id=order_id,
            event_type="order.created",
            from_state=None,
            to_state="created",
            payload={
                "customer_id": str(customer_id),
                "restaurant_id": str(restaurant_id),
                "total_amount": total_amount,
                "items": items,
            },
        )
    
    async def emit_state_changed(
        self,
        order_id: UUID,
        from_state: str,
        to_state: str,
        reason: Optional[str] = None,
    ) -> None:
        """Emit order.state_changed event."""
        await self.emit_order_event(
            order_id=order_id,
            event_type="order.state_changed",
            from_state=from_state,
            to_state=to_state,
            payload={"reason": reason} if reason else {},
        )


# Global producer instance (initialized in main.py)
kafka_producer: Optional[OrderKafkaProducer] = None


async def get_kafka_producer() -> OrderKafkaProducer:
    """Get the global Kafka producer instance."""
    global kafka_producer
    if kafka_producer is None:
        kafka_producer = OrderKafkaProducer()
        await kafka_producer.start()
    return kafka_producer