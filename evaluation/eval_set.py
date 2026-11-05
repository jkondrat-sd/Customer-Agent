"""Evaluation set for FlowDesk support agent."""

from typing import List, Dict, Any
from pydantic import BaseModel


class EvalCase(BaseModel):
    id: str
    query: str
    expected_intent: str
    expected_action_type: str | None = None
    expected_tool: str | None = None
    expected_guardrail_pass: bool | None = None
    expected_guardrail_errors: List[str] | None = None
    expected_confidence_min: float = 0.0
    description: str = ""


EVAL_CASES: List[EvalCase] = [
    EvalCase(
        id="faq_001",
        query="What is your return policy?",
        expected_intent="faq",
        expected_action_type=None,
        expected_tool=None,
        description="General FAQ about return policy",
    ),
    EvalCase(
        id="faq_002",
        query="How do I reset my password?",
        expected_intent="faq",
        expected_action_type="password_reset",
        expected_tool=None,
        description="Password reset FAQ",
    ),
    EvalCase(
        id="faq_003",
        query="What are your delivery times?",
        expected_intent="faq",
        expected_action_type=None,
        expected_tool=None,
        description="Delivery time FAQ",
    ),
    EvalCase(
        id="faq_004",
        query="Do you have a loyalty program?",
        expected_intent="faq",
        expected_action_type=None,
        expected_tool=None,
        description="Loyalty program FAQ",
    ),
    EvalCase(
        id="faq_005",
        query="How can I contact customer support?",
        expected_intent="faq",
        expected_action_type=None,
        expected_tool=None,
        description="Contact support FAQ",
    ),
    EvalCase(
        id="action_001",
        query="Where is my order order-12345?",
        expected_intent="action",
        expected_action_type="order_status",
        expected_tool="order_status",
        description="Order status lookup",
    ),
    EvalCase(
        id="action_002",
        query="Track my order 550e8400-e29b-41d4-a716-446655440000",
        expected_intent="action",
        expected_action_type="order_status",
        expected_tool="order_status",
        description="Order tracking with UUID",
    ),
    EvalCase(
        id="action_003",
        query="What is the status of my order?",
        expected_intent="action",
        expected_action_type="order_status",
        expected_tool="order_status",
        description="Generic order status (no ID)",
    ),
    EvalCase(
        id="refund_001",
        query="I want a refund for order order-12345 because the food was cold",
        expected_intent="action",
        expected_action_type="refund",
        expected_tool="refund_initiated",
        expected_guardrail_pass=True,
        description="Valid refund request",
    ),
    EvalCase(
        id="refund_002",
        query="Refund my order 550e8400-e29b-41d4-a716-446655440000 for $750 due to wrong order",
        expected_intent="action",
        expected_action_type="refund",
        expected_tool="refund_blocked",
        expected_guardrail_pass=False,
        expected_guardrail_errors=["exceeds maximum"],
        description="Refund amount exceeds $500 limit",
    ),
    EvalCase(
        id="refund_003",
        query="I want a $150 refund for order order-99999 because delivery was late",
        expected_intent="action",
        expected_action_type="refund",
        expected_tool="refund_initiated",
        expected_guardrail_pass=True,
        description="Refund requires human approval (>$100)",
    ),
    EvalCase(
        id="cancel_001",
        query="Cancel my order order-12345",
        expected_intent="action",
        expected_action_type="other",
        expected_tool="cancel_order",
        description="Order cancellation request",
    ),
    EvalCase(
        id="complex_001",
        query="I am extremely angry and want to speak to a manager immediately",
        expected_intent="complex",
        expected_action_type=None,
        expected_tool=None,
        description="Escalation - angry customer",
    ),
    EvalCase(
        id="complex_002",
        query="This is unacceptable, I demand a supervisor",
        expected_intent="complex",
        expected_action_type=None,
        expected_tool=None,
        description="Escalation - demanding supervisor",
    ),
    EvalCase(
        id="delay_001",
        query="My delivery is delayed, what can I do?",
        expected_intent="proactive_delay",
        expected_action_type=None,
        expected_tool=None,
        description="Proactive delay inquiry",
    ),
    EvalCase(
        id="delay_002",
        query="Why is my order late?",
        expected_intent="proactive_delay",
        expected_action_type=None,
        expected_tool=None,
        description="Delay reason inquiry",
    ),
    EvalCase(
        id="oos_001",
        query="Write me a Python script to scrape a website",
        expected_intent="out_of_scope",
        expected_action_type=None,
        expected_tool=None,
        description="Out of scope - coding request",
    ),
    EvalCase(
        id="oos_002",
        query="What is the capital of France?",
        expected_intent="out_of_scope",
        expected_action_type=None,
        expected_tool=None,
        description="Out of scope - general knowledge",
    ),
]


def get_eval_cases() -> List[EvalCase]:
    return EVAL_CASES


def get_eval_case_by_id(case_id: str) -> EvalCase | None:
    for case in EVAL_CASES:
        if case.id == case_id:
            return case
    return None


def get_eval_stats() -> Dict[str, Any]:
    total = len(EVAL_CASES)
    by_intent: Dict[str, int] = {}
    for case in EVAL_CASES:
        by_intent[case.expected_intent] = by_intent.get(case.expected_intent, 0) + 1
    return {
        "total_cases": total,
        "by_intent": by_intent,
        "guardrail_cases": sum(1 for c in EVAL_CASES if c.expected_guardrail_pass is not None),
        "tool_calling_cases": sum(1 for c in EVAL_CASES if c.expected_tool is not None),
    }


if __name__ == "__main__":
    import json
    stats = get_eval_stats()
    print(json.dumps(stats, indent=2))
    print(f"\nTotal cases: {len(EVAL_CASES)}")
    for case in EVAL_CASES:
        print(f"  {case.id}: {case.query[:60]}... -> {case.expected_intent}")