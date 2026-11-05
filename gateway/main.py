"""FastAPI gateway — API layer for the FlowDesk support platform.

Endpoints (build_guide §4.1):
- POST /chat      — synchronous chat with the orchestrator
- POST /chat/stream — SSE streaming response (stretch goal)
- POST /feedback  — thumbs up/down user feedback (stretch goal)
- GET  /health    — health check for Cloud Run
"""

from __future__ import annotations

import logging
import uuid

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import gradio as gr
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from typing import Optional

from db.session import log_feedback
from db.checkpointer import get_checkpointer
from orchestrator.graph import graph
from gateway.streaming import generate_sse_stream

@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_checkpointer() as memory:
        app.state.compiled_graph = graph.compile(checkpointer=memory)
        yield

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FlowDesk Support API",
    description="LLMOps-driven Customer Support Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    confidence: float
    intent: Optional[str] = None
    retry_count: int = 0


class DemoChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    conversation_id: Optional[str] = None
    message_content: str
    response_content: str
    rating: str  # "up" or "down"


class FeedbackResponse(BaseModel):
    status: str
    feedback_id: str


# ---------------------------------------------------------------------------
# POST /chat — synchronous chat (build_guide §4.1)
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    """Submit a message to the support orchestrator and receive an intelligent response.

    Maintains conversation state across requests using the provided conversation_id.
    """
    try:
        if not req.conversation_id:
            req.conversation_id = str(uuid.uuid4())

        thread_config = {"configurable": {"thread_id": req.conversation_id}}

        initial_state = {"messages": [HumanMessage(content=req.message)]}
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: request.app.state.compiled_graph.invoke(initial_state, config=thread_config)
        )

        ai_message = (
            result["messages"][-1].content
            if result.get("messages")
            else "I'm sorry, an error occurred."
        )
        confidence = result.get("confidence", 0.0)
        intent = result.get("intent", "unknown")
        retry_count = result.get("retry_count", 0)

        return ChatResponse(
            response=ai_message,
            confidence=confidence,
            intent=intent,
            retry_count=retry_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /api/chat — SSE streaming for Next.js Demo Frontend
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def api_chat_stream(req: DemoChatRequest, request: Request) -> StreamingResponse:
    """Stream the orchestrator response for the demo frontend.
    
    NOTE: Simulated Streaming (Option A).
    Because Groq + Cohere reranking is so fast (<1s TTFT), we fetch the full
    response synchronously and simulate the stream by chunking the text. This
    guarantees metadata integrity without risking complex on-the-fly JSON parsing
    from partial tool-call streams.
    """
    conversation_id = req.session_id if req.session_id else str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": conversation_id}}
    initial_state = {"messages": [HumanMessage(content=req.message)]}
    
    return StreamingResponse(
        generate_sse_stream(request.app.state.compiled_graph, initial_state, thread_config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /feedback — user feedback (stretch goal, build_guide §7)
# ---------------------------------------------------------------------------


@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(req: FeedbackRequest) -> FeedbackResponse:
    """Record user feedback (thumbs up/down) on an agent response.

    Stored in the feedback table for evaluation and future fine-tuning.
    """
    if req.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")

    feedback_id = log_feedback(
        rating=req.rating,
        response_content=req.response_content,
        message_content=req.message_content,
        conversation_id=req.conversation_id,
    )
    if feedback_id:
        return FeedbackResponse(
            status="recorded",
            feedback_id=feedback_id,
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to record feedback")


# ---------------------------------------------------------------------------
# GET /health — health check (build_guide §4.1)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for Cloud Run and load balancers."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Mount Gradio demo at root — accessible at Service URL /
# ---------------------------------------------------------------------------

from gateway.demo import demo as gradio_demo  # noqa: E402

app = gr.mount_gradio_app(app, gradio_demo, path="/")

