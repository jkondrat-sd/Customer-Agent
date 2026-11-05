from langgraph.graph import END
from orchestrator.graph import route_after_router, route_after_rag
from orchestrator.state import SupportState

def test_route_after_router():
    state: SupportState = {"intent": "faq", "messages": [], "retrieved_context": [], "confidence": 0.0, "retry_count": 0}
    assert route_after_router(state) == "rag_agent"
    
    state["intent"] = "action"
    assert route_after_router(state) == "action_agent"
    
    state["intent"] = "complex"
    assert route_after_router(state) == "escalation_agent"

def test_route_after_rag():
    # Low confidence, 0 retries -> retry
    state: SupportState = {"intent": "faq", "messages": [], "retrieved_context": [], "confidence": 0.5, "retry_count": 0}
    assert route_after_rag(state) == "rag_agent"
    
    # Low confidence, 2 retries -> END
    state["retry_count"] = 2
    assert route_after_rag(state) == END
    
    # High confidence -> END
    state["confidence"] = 0.9
    state["retry_count"] = 0
    assert route_after_rag(state) == END
