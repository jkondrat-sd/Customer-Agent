"""Action tools for calling real Order and Refund APIs."""

from __future__ import annotations

import httpx
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ORDER_SERVICE_URL = "http://localhost:8001"
REFUND_SERVICE_URL = "http://localhost:8002"


class OrderStatusResult(BaseModel):
    order_id: str
    state: str
    total_amount: str
    currency: str
    created_at: str
    delivered_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancellation_reason: Optional[str] = None


class RefundResult(BaseModel):
    refund_id: str
    order_id: str
    state: str
    amount: str
    currency: str
    reason: str
    requires_approval: bool


class ActionTools:
    def __init__(self, order_service_url: str = ORDER_SERVICE_URL, refund_service_url: str = REFUND_SERVICE_URL):
        self.order_service_url = order_service_url
        self.refund_service_url = refund_service_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_order_status(self, order_id: str) -> OrderStatusResult:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.order_service_url}/orders/{order_id}")
            resp.raise_for_status()
            data = resp.json()
            return OrderStatusResult(
                order_id=str(data["id"]),
                state=data["state"],
                total_amount=data["total_amount"],
                currency=data.get("currency", "USD"),
                created_at=data["created_at"],
                delivered_at=data.get("delivered_at"),
                cancelled_at=data.get("cancelled_at"),
                cancellation_reason=data.get("cancellation_reason"),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Order {order_id} not found")
            logger.error(f"Order service error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            raise

    async def initiate_refund(
        self,
        order_id: str,
        customer_id: str,
        amount: str,
        reason: str,
        idempotency_key: str,
        reason_details: Optional[str] = None,
    ) -> RefundResult:
        client = await self._get_client()
        try:
            payload = {
                "order_id": order_id,
                "customer_id": customer_id,
                "amount": amount,
                "reason": reason,
                "idempotency_key": idempotency_key,
            }
            if reason_details:
                payload["reason_details"] = reason_details

            resp = await client.post(f"{self.refund_service_url}/refunds", json=payload)
            
            if resp.status_code == 409:
                raise ValueError(f"Refund already exists for order {order_id}")
            if resp.status_code == 400:
                error_detail = resp.json().get("detail", "Unknown error")
                raise ValueError(f"Refund request rejected: {error_detail}")
            
            resp.raise_for_status()
            data = resp.json()
            return RefundResult(
                refund_id=str(data["id"]),
                order_id=str(data["order_id"]),
                state=data["state"],
                amount=data["amount"],
                currency=data.get("currency", "USD"),
                reason=data["reason"],
                requires_approval=data.get("requires_approval", False),
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Refund service error: {e}")
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to initiate refund: {e}")
            raise

    async def get_refund_status(self, refund_id: str) -> RefundResult:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.refund_service_url}/refunds/{refund_id}")
            resp.raise_for_status()
            data = resp.json()
            return RefundResult(
                refund_id=str(data["id"]),
                order_id=str(data["order_id"]),
                state=data["state"],
                amount=data["amount"],
                currency=data.get("currency", "USD"),
                reason=data["reason"],
                requires_approval=data.get("requires_approval", False),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Refund {refund_id} not found")
            logger.error(f"Refund service error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to get refund status: {e}")
            raise

    async def cancel_order(self, order_id: str, reason: Optional[str] = None) -> OrderStatusResult:
        client = await self._get_client()
        try:
            payload = {"reason": reason} if reason else {}
            resp = await client.post(
                f"{self.order_service_url}/orders/{order_id}/cancel",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return OrderStatusResult(
                order_id=str(data["id"]),
                state=data["state"],
                total_amount=data["total_amount"],
                currency=data.get("currency", "USD"),
                created_at=data["created_at"],
                delivered_at=data.get("delivered_at"),
                cancelled_at=data.get("cancelled_at"),
                cancellation_reason=data.get("cancellation_reason"),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Order {order_id} not found")
            if e.response.status_code == 400:
                error_detail = e.response.json().get("detail", "Unknown error")
                raise ValueError(f"Cannot cancel order: {error_detail}")
            logger.error(f"Order service error: {e}")
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            raise


action_tools: Optional[ActionTools] = None


async def get_action_tools() -> ActionTools:
    global action_tools
    if action_tools is None:
        action_tools = ActionTools()
    return action_tools