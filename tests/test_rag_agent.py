from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from orchestrator.agents.rag_agent import rag_agent_node
from orchestrator.state import SupportState
from orchestrator.models import RAGResponse

@patch("orchestrator.agents.rag_agent.hybrid_search")
@patch("orchestrator.agents.rag_agent.rerank")
@patch("orchestrator.agents.rag_agent.ChatGroq")
def test_rag_agent_short_query(mock_chat_groq, mock_rerank, mock_hybrid_search):
    mock_hybrid_search.return_value = []
    mock_rerank.return_value = [{"text": "Context text", "score": 0.85}]
    
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = RAGResponse(answer="Yes", confidence=0.9)
    mock_llm.with_structured_output.return_value = mock_structured
    mock_chat_groq.return_value = mock_llm

    state: SupportState = {
        "messages": [HumanMessage(content="Short query?")], 
        "intent": "faq", 
        "retrieved_context": [], 
        "confidence": 0.0, 
        "retry_count": 0
    }
    
    new_state = rag_agent_node(state)
    assert len(new_state["messages"]) == 1
    assert new_state["messages"][0].content == "Yes"
    assert new_state["confidence"] == 0.925
    assert new_state["retry_count"] == 1
    assert "Context text" in new_state["retrieved_context"]

@patch("orchestrator.agents.rag_agent.ChatGoogleGenerativeAI")
def test_rag_agent_retry(mock_chat_gemini):
    # If retry_count > 0, should use Gemini
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = RAGResponse(answer="Gemini answer", confidence=0.8)
    mock_llm.with_structured_output.return_value = mock_structured
    mock_chat_gemini.return_value = mock_llm

    state: SupportState = {
        "messages": [HumanMessage(content="Short query?")], 
        "intent": "faq", 
        "retrieved_context": ["Old context"], 
        "confidence": 0.5, 
        "retry_count": 1
    }
    
    with patch("orchestrator.agents.rag_agent.hybrid_search") as mock_hybrid, \
         patch("orchestrator.agents.rag_agent.rerank") as mock_rerank:
        mock_hybrid.return_value = []
        mock_rerank.return_value = [{"text": "New context text", "score": 0.9}]
        
        new_state = rag_agent_node(state)
        
        assert new_state["messages"][0].content == "Gemini answer"
        assert new_state["retry_count"] == 2
        mock_chat_gemini.assert_called_once()
