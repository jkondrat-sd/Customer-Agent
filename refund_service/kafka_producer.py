"""Kafka producer for refund service events."""

import json
import logging
from typing import Optional
from datetime import datetime
from uuid import UUID

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


class RefundKafkaProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer: Optional[AIOKafkaProducer] = None
        self.topic = "refund.events"
    
    async def start(self) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await self.producer.start()
        logger.info("Refund Kafka producer started")
    
    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()
            logger.info("Refund Kafka producer stopped")
    
    async def emit_refund_event(
        self,
        refund_id: UUID,
        event_type: str,
        from_state: Optional[str],
        to_state: str,
        payload: Optional[dict] = None,
    ) -> None:
        if not self.producer:
            logger.warning("Kafka producer not started, skipping event emission")
            return
        
        event = {
            "refund_id": str(refund_id),
            "event_type": event_type,
            "from_state": from_state,
            "to_state": to_state,
            "payload": payload or {},
            "timestamp": datetime.utcnow().isoformat(),
            "service": "refund-service",
        }
        
        try:
            await self.producer.send_and_wait(
                self.topic,
                key=str(refund_id),
                value=event,
            )
            logger.debug(f"Emitted refund event: {event_type} for refund {refund_id}")
        except KafkaError as e:
            logger.error(f"Failed to emit refund event: {e}")


kafka_producer: Optional[RefundKafkaProducer] = None


async def get_kafka_producer() -> RefundKafkaProducer:
    global kafka_producer
    if kafka_producer is None:
        kafka_producer = RefundKafkaProducer()
        await kafka_producer.start()
    return kafka_producer