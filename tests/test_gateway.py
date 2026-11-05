from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from gateway.main import app
import uuid
import pytest

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# We'll mock the compiled graph on app.state to avoid live LLM calls
@pytest.fixture
def mock_graph():
    # Assign the mock graph directly to app.state
    mock_g = AsyncMock()
    app.state.compiled_graph = mock_g
    return mock_g

@pytest.mark.asyncio
async def test_chat_endpoint_success(mock_graph):
    from langchain_core.messages import AIMessage
    
    from unittest.mock import MagicMock
    # invoke is synchronous now
    mock_graph.invoke = MagicMock(return_value={
        "messages": [AIMessage(content="Hello from mock!")],
        "confidence": 0.95,
        "intent": "faq",
        "retry_count": 0
    })
    
    conv_id = str(uuid.uuid4())
    payload = {
        "conversation_id": conv_id,
        "message": "Hi there"
    }
    
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["response"] == "Hello from mock!"
    assert data["confidence"] == 0.95
    assert data["intent"] == "faq"
    assert data["retry_count"] == 0

def test_chat_endpoint_missing_body():
    response = client.post("/chat", json={})
    # Should fail validation
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Feedback endpoint tests (build_guide stretch goal)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_log_feedback(mocker):
    """Mock log_feedback for feedback tests."""
    mock_log = mocker.patch("gateway.main.log_feedback", return_value=str(uuid.uuid4()))
    return mock_log


def test_feedback_thumbs_up(mock_log_feedback):
    payload = {
        "message_content": "How do I reset my password?",
        "response_content": "Go to Settings > Security > Change Password.",
        "rating": "up",
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "recorded"
    assert "feedback_id" in data


def test_feedback_thumbs_down(mock_log_feedback):
    payload = {
        "message_content": "What is my order status?",
        "response_content": "I am the action agent.",
        "rating": "down",
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "recorded"


def test_feedback_invalid_rating():
    payload = {
        "message_content": "test",
        "response_content": "test",
        "rating": "invalid",
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 400
