"""Delivery Simulator configuration."""

import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ORDER_EVENTS_TOPIC = os.getenv("ORDER_EVENTS_TOPIC", "order.events")
DELIVERY_EVENTS_TOPIC = os.getenv("DELIVERY_EVENTS_TOPIC", "delivery.events")
DELAY_PROBABILITY = float(os.getenv("DELAY_PROBABILITY", "0.3"))
DELAY_MIN_MINUTES = int(os.getenv("DELAY_MIN_MINUTES", "15"))
DELAY_MAX_MINUTES = int(os.getenv("DELAY_MAX_MINUTES", "120"))