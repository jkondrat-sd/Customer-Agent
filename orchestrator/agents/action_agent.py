"""Action agent — handles account actions, order lookups, refunds, password resets.

Architecture rules (skill.md):
- §3: Uses Groq for short/simple/single-turn action queries (latency-sensitive).
- §4: Every agent response carries a confidence score via structured output.
- §6: All decisions logged to PostgreSQL.
- §7: Real API calls to Order and Refund services with refund guardrails.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from db.session import log_telemetry
from orchestrator.models import ActionResponse
from orchestrator.state import SupportState
from orchestrator.agents.tools import ActionTools, get_action_tools

logger = logging.getLogger(__name__)

# Pre-load relevant knowledge base docs so the agent can ground its answers
_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
_ACTION_DOCS: dict[str, str] = {}

for _doc_name in ("password_security.md", "return_refund_policy.md",
                   "account_management.md", "billing_payments.md",
                   "shipping_delivery.md"):
    _path = _DOCS_DIR / _doc_name
    if _path.exists():
        _ACTION_DOCS[_doc_name] = _path.read_text(encoding="utf-8")

# Refund guardrail constants
MAX_REFUND_AMOUNT = 500.00
HUMAN_APPROVAL_THRESHOLD = 100.00
REFUND_WINDOW_DAYS = 30


class OrderInfo(BaseModel):
    """Extracted order information from user query."""
    order_id: Optional[str] = None
    customer_id: Optional[str] = None
    amount: Optional[float] = None
    reason: Optional[str] = None
    action_type: str


def _extract_order_info(query: str) -> OrderInfo:
    """Extract order-related information from user query using regex patterns."""
    action_type = "other"
    
    if re.search(r'\brefund\b', query, re.IGNORECASE):
        action_type = "refund"
    elif re.search(r'\bcancel\b', query, re.IGNORECASE):
        action_type = "cancel_order"
    elif re.search(r'\b(order|status|track|where is)\b', query, re.IGNORECASE):
        action_type = "order_status"
    
    order_id_match = re.search(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|order[-_ ]?\d+',
        query, re.IGNORECASE
    )
    order_id = order_id_match.group(0) if order_id_match else None
    
    amount_match = re.search(r'\$?(\d+\.?\d*)', query)
    amount = float(amount_match.group(1)) if amount_match else None
    
    reason_match = re.search(r'(?:because|due to|reason:?)\s+(.+?)(?:\.|$)', query, re.IGNORECASE)
    reason = reason_match.group(1).strip() if reason_match else None
    
    return OrderInfo(
        order_id=order_id,
        amount=amount,
        reason=reason,
        action_type=action_type,
    )


def _apply_refund_guardrails(
    order_info: OrderInfo,
    order_status: Optional[dict] = None,
) -> dict:
    """Apply refund guardrails and return guardrail result."""
    guardrail_result = {
        "passed": True,
        "errors": [],
        "warnings": [],
        "requires_approval": False,
        "requires_confirmation": False,
    }
    
    if order_info.action_type != "refund":
        return guardrail_result
    
    if order_info.amount is not None:
        if order_info.amount > MAX_REFUND_AMOUNT:
            guardrail_result["passed"] = False
            guardrail_result["errors"].append(
                f"Refund amount ${order_info.amount:.2f} exceeds maximum ${MAX_REFUND_AMOUNT:.2f}"
            )
        if order_info.amount > HUMAN_APPROVAL_THRESHOLD:
            guardrail_result["requires_approval"] = True
            guardrail_result["warnings"].append(
                f"Refund ${order_info.amount:.2f} requires human agent approval"
            )
    
    if order_status:
        state = order_status.get("state", "")
        if state != "delivered":
            guardrail_result["passed"] = False
            guardrail_result["errors"].append(
                f"Order must be delivered for refund (current: {state})"
            )
        if state == "delivered" and order_status.get("delivered_at"):
            from datetime import datetime, timezone
            delivered_at = datetime.fromisoformat(order_status["delivered_at"].replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - delivered_at).days
            if days_since > REFUND_WINDOW_DAYS:
                guardrail_result["passed"] = False
                guardrail_result["errors"].append(
                    f"Refund window expired ({REFUND_WINDOW_DAYS} days from delivery)"
                )
    
    if order_info.action_type == "refund" and guardrail_result["passed"]:
        guardrail_result["requires_confirmation"] = True
    
    return guardrail_result


def action_agent_node(state: SupportState) -> SupportState:
    """Action agent node — real LLM-powered tool-calling for account actions."""
    messages = state.get("messages", [])
    if not messages:
        return state

    last_message = messages[-1]
    query = last_message.content if hasattr(last_message, "content") else str(last_message)

    order_info = _extract_order_info(query)
    logger.info(f"Action agent extracted: {order_info.action_type}, order_id={order_info.order_id}")

    context_str = "\n\n---\n\n".join(
        f"## {name}\n{content}" for name, content in _ACTION_DOCS.items()
    )

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    structured_llm = llm.with_structured_output(ActionResponse)

    import asyncio
    try:
        tools = asyncio.run(get_action_tools())
    except RuntimeError:
        tools = ActionTools()

    api_result = None
    guardrail_result = {"passed": True, "errors": [], "warnings": [],
                        "requires_approval": False, "requires_confirmation": False}
    order_status = None

    try:
        if order_info.action_type == "order_status" and order_info.order_id:
            order_status = tools.get_order_status(order_info.order_id)
            api_result = {
                "action": "order_status",
                "order_id": order_info.order_id,
                "state": order_status.state,
                "total_amount": order_status.total_amount,
                "delivered_at": order_status.delivered_at,
            }

        elif order_info.action_type == "refund" and order_info.order_id:
            try:
                order_status = tools.get_order_status(order_info.order_id)
                order_status_dict = {
                    "state": order_status.state,
                    "delivered_at": order_status.delivered_at,
                    "total_amount": order_status.total_amount,
                }
            except Exception:
                order_status_dict = None

            guardrail_result = _apply_refund_guardrails(order_info, order_status_dict)

            if guardrail_result["passed"]:
                idempotency_key = str(uuid.uuid4())
                customer_id = order_info.customer_id or str(uuid.uuid4())
                refund_result = tools.initiate_refund(
                    order_id=order_info.order_id,
                    customer_id=customer_id,
                    amount=str(order_info.amount or "0.00"),
                    reason=order_info.reason or "Customer request",
                    idempotency_key=idempotency_key,
                )
                api_result = {
                    "action": "refund_initiated",
                    "refund_id": refund_result.refund_id,
                    "order_id": order_info.order_id,
                    "state": refund_result.state,
                    "amount": refund_result.amount,
                    "requires_approval": refund_result.requires_approval,
                }
            else:
                api_result = {
                    "action": "refund_blocked",
                    "errors": guardrail_result["errors"],
                    "requires_approval": guardrail_result["requires_approval"],
                    "requires_confirmation": guardrail_result["requires_confirmation"],
                }

        elif order_info.action_type == "cancel_order" and order_info.order_id:
            cancel_result = tools.cancel_order(order_info.order_id)
            api_result = {
                "action": "order_cancelled",
                "order_id": order_info.order_id,
                "state": cancel_result.state,
                "cancellation_reason": cancel_result.cancellation_reason,
            }

    except ValueError as e:
        api_result = {"action": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Action agent API call failed: {e}")
        api_result = {"action": "error", "error": "Service temporarily unavailable"}

    # Build prompt with API results and guardrail info
    api_context = ""
    if api_result:
        api_context = f"\n\nAPI Result:\n{api_result}\n"

    guardrail_context = ""
    if guardrail_result["errors"]:
        guardrail_context = f"\n\nGuardrail Errors:\n{guardrail_result['errors']}\n"
    if guardrail_result["warnings"]:
        guardrail_context += f"\nGuardrail Warnings:\n{guardrail_result['warnings']}\n"
    if guardrail_result["requires_approval"]:
        guardrail_context += "\nRequires human agent approval.\n"
    if guardrail_result["requires_confirmation"]:
        guardrail_context += "\nRequires customer confirmation before proceeding.\n"

    prompt = f"""You are a customer support action agent for FlowDesk. The user needs help with a specific account action.

Based on the knowledge base documentation and API results below, provide a clear, step-by-step response.

CRITICAL: The confidence score MUST be a raw number (e.g., 0.0 or 1.0). Do not enclose it in quotes.

Knowledge Base:
{context_str}

User Request:
{query}
{api_context}
{guardrail_context}

Respond with a helpful, actionable answer. If the action was blocked by guardrails, explain why and what the customer needs to do. If human approval is required, explain that a human agent will review the request. Classify the action_type as one of: 'password_reset', 'order_status', 'refund', 'account_management', or 'other'."""

    try:
        response = structured_llm.invoke(prompt)
        answer = response.answer
        try:
            llm_confidence = float(response.confidence)
        except (ValueError, TypeError):
            llm_confidence = 0.0
        _action_type = response.action_type
    except Exception as e:
        logger.error("Action agent LLM call failed: %s", e)
        answer = (
            "I apologize, but I'm having trouble processing your request right now. "
            "Please try again or contact support@flowdesk.com for immediate assistance."
        )
        llm_confidence = 0.0

    # Log to PostgreSQL with guardrail info
    log_telemetry(
        answer=answer,
        llm_confidence=llm_confidence,
        retrieval_score=1.0,
        final_confidence=llm_confidence,
    )

    return {
        "messages": [AIMessage(content=answer)],
        "confidence": llm_confidence,
    }