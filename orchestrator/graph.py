"""LangGraph orchestrator — stateful multi-agent graph.

Architecture (build_guide §2.2):
- Router → classifies intent (faq / action / complex)
- RAG Agent → hybrid retrieval + reranking + LLM (Groq or Gemini)
- Action Agent → tool-calling for account actions (Groq)
- Escalation Agent → human handoff with DB logging

Self-correction (skill.md §5): retry ceiling of 2 before escalating.
Checkpointer (build_guide §2.2): PostgreSQL in prod, SQLite for local dev.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph


from orchestrator.agents.action_agent import action_agent_node
from orchestrator.agents.escalation_agent import escalation_agent_node
from orchestrator.agents.rag_agent import rag_agent_node
from orchestrator.agents.router import route_intent
from orchestrator.state import SupportState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

graph = StateGraph(SupportState)

# Add nodes
graph.add_node("router", route_intent)
graph.add_node("rag_agent", rag_agent_node)
graph.add_node("action_agent", action_agent_node)
graph.add_node("escalation_agent", escalation_agent_node)


# Conditional routing from intent (build_guide §2.2)
def route_after_router(state: SupportState) -> str:
    intent = state.get("intent", "faq")
    if intent == "faq":
        return "rag_agent"
    elif intent in ("action", "proactive_delay"):
        return "action_agent"
    else:
        return "escalation_agent"


graph.add_conditional_edges("router", route_after_router)


# RAG self-correction logic (skill.md §5: retry ceiling, build_guide §3.2)
def route_after_rag(state: SupportState) -> str:
    confidence = state.get("confidence", 1.0)
    retry_count = state.get("retry_count", 0)

    if confidence < 0.6 and retry_count < 2:
        return "rag_agent"  # retry with wider search / model switch
    return END


graph.add_conditional_edges("rag_agent", route_after_rag)

# Action and escalation just end
graph.add_edge("action_agent", END)
graph.add_edge("escalation_agent", END)

# Set entry point
graph.set_entry_point("router")

# ---------------------------------------------------------------------------
# Checkpointer: PostgreSQL in prod, SQLite for local dev (build_guide §2.2)
# ---------------------------------------------------------------------------
# Note: Graph compilation with checkpointer is deferred to entrypoints 
# to avoid forcing DB connections at module import time.
