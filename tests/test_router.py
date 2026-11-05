from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from orchestrator.agents.router import route_intent
from orchestrator.state import SupportState
from orchestrator.models import IntentClassification

@patch("orchestrator.agents.router.ChatGroq")
def test_route_intent_faq(mock_chat_groq):
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = IntentClassification(intent="faq")
    mock_llm.with_structured_output.return_value = mock_structured
    mock_chat_groq.return_value = mock_llm

    state: SupportState = {"messages": [HumanMessage(content="How do I return?")], "intent": "", "retrieved_context": [], "confidence": 0.0, "retry_count": 0}
    new_state = route_intent(state)
    assert new_state["intent"] == "faq"

@patch("orchestrator.agents.router.ChatGroq")
def test_route_intent_empty(mock_chat_groq):
    state: SupportState = {"messages": [], "intent": "", "retrieved_context": [], "confidence": 0.0, "retry_count": 0}
    new_state = route_intent(state)
    assert new_state["intent"] == "faq"
    mock_chat_groq.assert_not_called()
