from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from orchestrator.state import SupportState
from orchestrator.models import RAGResponse
from retrieval.hybrid_retriever import hybrid_search
from retrieval.reranker import rerank
from evaluation.confidence_scorer import compute_unified_confidence
from db.session import log_telemetry
import config
import logging

logger = logging.getLogger(__name__)

def _perform_retrieval(query: str, retry_count: int) -> tuple[list[str], list[dict], list[float]]:
    """Perform hybrid search and reranking."""
    search_top_k = config.settings.retrieval_top_k * 2 if retry_count > 0 else config.settings.retrieval_top_k
    candidates = hybrid_search(query, top_k=search_top_k)
    reranked = rerank(query, candidates, top_n=config.settings.rerank_top_n)
    
    retrieved_context = [doc["text"] for doc in reranked]
    retrieved_chunks = [{"source": doc.get("source", ""), "score": float(doc.get("score", 0.0))} for doc in reranked]
    rerank_scores = [doc["score"] for doc in reranked]
    
    return retrieved_context, retrieved_chunks, rerank_scores

def _generate_answer(query: str, context_str: str, retry_count: int, is_multi_turn: bool) -> tuple[str, float]:
    """Route to appropriate LLM and generate answer based on context."""
    is_short = len(query) < 200
    
    if is_short and not is_multi_turn and retry_count == 0:
        logger.info("Using Groq for RAG (short query, single turn)")
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    else:
        logger.info(f"Using Gemini for RAG (retry={retry_count}, multi_turn={is_multi_turn}, length={len(query)})")
        llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
        
    structured_llm = llm.with_structured_output(RAGResponse)
    
    prompt = f"""
    You are a helpful customer support assistant. Answer the user's question based ONLY on the following context.
    If the context does not contain the answer, say "I don't know" and give a low confidence score (e.g. 0.0).
    
    CRITICAL: The confidence score MUST be a raw number (e.g., 0.0 or 1.0). Do not enclose it in quotes.
    
    Context:
    {context_str}
    
    User Question:
    {query}
    """
    
    response = structured_llm.invoke(prompt)
    
    if response:
        answer = response.answer
        try:
            llm_confidence = float(response.confidence)
        except (ValueError, TypeError):
            llm_confidence = 0.0
    else:
        answer = "I'm sorry, I couldn't generate a response."
        llm_confidence = 0.0
        
    return answer, llm_confidence

def rag_agent_node(state: SupportState) -> SupportState:
    """
    RAG agent node:
    1. Hybrid search + reranking
    2. Model selection (Groq for short/initial, Gemini for long/retry)
    3. Generate answer based ONLY on retrieved context
    4. Provide a confidence score
    """
    messages = state.get("messages", [])
    if not messages:
        return state
        
    last_message = messages[-1]
    query = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    retrieved_context = state.get("retrieved_context", [])
    retrieved_chunks = state.get("retrieved_chunks", [])
    retry_count = state.get("retry_count", 0)
    
    # 1. Retrieval
    rerank_scores = []
    if not retrieved_context or retry_count > 0:
        retrieved_context, retrieved_chunks, rerank_scores = _perform_retrieval(query, retry_count)
        
    context_str = "\n\n".join(retrieved_context)
    
    # 2. Model Routing & Generation
    is_multi_turn = len(messages) > 1
    answer, llm_confidence = _generate_answer(query, context_str, retry_count, is_multi_turn)
        
    # 3. Confidence Scoring
    max_retrieval_score = rerank_scores[0] if rerank_scores else 0.5
    
    final_confidence = compute_unified_confidence(
        retrieval_score=max_retrieval_score,
        llm_confidence=llm_confidence,
        answer=answer,
        retrieved_context=retrieved_context
    )
    
    # 4. Telemetry
    log_telemetry(
        answer=answer,
        query=query,
        llm_confidence=llm_confidence,
        retrieval_score=max_retrieval_score,
        final_confidence=final_confidence,
        retrieved_chunks=retrieved_context,
        rerank_scores=rerank_scores
    )
        
    return {
        "messages": [AIMessage(content=answer)],
        "retrieved_context": retrieved_context,
        "retrieved_chunks": retrieved_chunks,
        "confidence": final_confidence,
        "retry_count": retry_count + 1
    }
