from orchestrator.state import SupportState

def test_support_state_initialization():
    state: SupportState = {
        "messages": [],
        "intent": "faq",
        "retrieved_context": [],
        "confidence": 0.0,
        "retry_count": 0
    }
    assert state["intent"] == "faq"
    assert len(state["messages"]) == 0
