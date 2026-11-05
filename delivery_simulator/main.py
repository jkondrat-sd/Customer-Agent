"""Delivery Simulator - simulates delivery events with delays."""

import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
ORDER_EVENTS_TOPIC = "order.events"
DELIVERY_EVENTS_TOPIC = "delivery.events"

# Delivery delay configuration
DELAY_PROBABILITY = 0.3  # 30% chance of delay
DELAY_MIN_MINUTES = 15
DELAY_MAX_MINUTES = 120


class DeliverySimulator:
    """Simulates delivery lifecycle with possible delays."""
    
    def __init__(self):
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.running = False
    
    async def start(self):
        self.consumer = AIOKafkaConsumer(
            ORDER_EVENTS_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id="delivery-simulator",
            auto_offset_reset="latest",
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await self.consumer.start()
        await self.producer.start()
        logger.info("Delivery Simulator started")
    
    async def stop(self):
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Delivery Simulator stopped")
    
    async def run(self):
        self.running = True
        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                await self._process_order_event(msg.value)
        except Exception as e:
            logger.error(f"Delivery simulator error: {e}")
    
    async def _process_order_event(self, event: dict):
        event_type = event.get("event_type", "")
        
        # Only react to shipped orders
        if event_type != "order.state_changed" or event.get("to_state") != "shipped":
            return
        
        order_id = event.get("order_id")
        logger.info(f"Processing delivery for order {order_id}")
        
        # Simulate delivery stages with possible delay
        await self._simulate_delivery(order_id)
    
    async def _simulate_delivery(self, order_id: str):
        # Stage 1: In transit
        await self._emit_delivery_event(order_id, "in_transit", "delivery.in_transit")
        
        # Simulate transit time
        transit_delay = random.uniform(2, 10)  # seconds to simulate transit
        await asyncio.sleep(transit_delay)
        
        # Decide if delayed
        is_delayed = random.random() < DELAY_PROBABILITY
        
        if is_delayed:
            delay_minutes = random.randint(DELAY_MIN_MINUTES, DELAY_MAX_MINUTES)
            reason = random.choice([
                "weather_conditions",
                "carrier_issue",
                "traffic",
                "restaurant_delay",
            ])
            await self._emit_delivery_event(
                order_id, 
                "delayed", 
                "delivery.delayed",
                delay_minutes=delay_minutes,
                reason=reason,
            )
            logger.warning(f"Order {order_id} delayed by {delay_minutes} minutes: {reason}")
            
            # Wait for delay duration then deliver
            await asyncio.sleep(min(delay_minutes / 60, 5))  # Cap simulation wait
        else:
            # No delay, proceed to out_for_delivery
            await self._emit_delivery_event(order_id, "out_for_delivery", "delivery.out_for_delivery")
            await asyncio.sleep(1)
        
        # Stage: Delivered
        await self._emit_delivery_event(order_id, "delivered", "delivery.delivered")
        logger.info(f"Order {order_id} delivered")
    
    async def _emit_delivery_event(
        self,
        order_id: str,
        status: str,
        event_type: str,
        delay_minutes: Optional[int] = None,
        reason: Optional[str] = None,
    ):
        event = {
            "order_id": order_id,
            "status": status,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "delivery-simulator",
        }
        if delay_minutes:
            event["delay_minutes"] = delay_minutes
        if reason:
            event["reason"] = reason
        
        try:
            await self.producer.send_and_wait(
                DELIVERY_EVENTS_TOPIC,
                key=order_id,
                value=event,
            )
            logger.debug(f"Emitted delivery event: {event_type} for order {order_id}")
        except KafkaError as e:
            logger.error(f"Failed to emit delivery event: {e}")


async def main():
    simulator = DeliverySimulator()
    await simulator.start()
    try:
        await simulator.run()
    except KeyboardInterrupt:
        pass
    finally:
        await simulator.stop()


if __name__ == "__main__":
    asyncio.run(main())