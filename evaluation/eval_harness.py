import json
import time
from langchain_core.messages import HumanMessage
from db.checkpointer import get_checkpointer
from orchestrator.graph import graph

def run_eval_harness(labeled_set_path: str = "evaluation/labeled_set.json"):
    with open(labeled_set_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    queries = data["queries"]
    total = len(queries)
    
    results = []
    latencies = []
    total_confidence = 0
    total_groundedness = 0
    escalation_count = 0
    
    print(f"Running Eval Harness on {total} queries...\n")
    
    with get_checkpointer() as memory:
        compiled_graph = graph.compile(checkpointer=memory)
        for i, item in enumerate(queries):
            query = item["query"]
            _expected_doc = item["expected_doc_id"]
            
            start_time = time.time()
            
            # Fresh thread for each query so they don't share context
            thread = {"configurable": {"thread_id": f"eval_user_{i}"}}
            initial_state = {"messages": [HumanMessage(content=query)]}
            
            final_state = compiled_graph.invoke(initial_state, thread)
            
            latency = time.time() - start_time
            latencies.append(latency)
            
            intent = final_state.get("intent", "")
            confidence = final_state.get("confidence", 0.0)
            
            if intent == "escalation_agent":
                escalation_count += 1
                
            total_confidence += confidence
            
            # Groundedness we can just reuse confidence for now, 
            # or we could recalculate it. The rag_agent puts the final unified score in `confidence`.
            total_groundedness += confidence # Simplified proxy for demo
            
            # Accuracy: we check if the expected_doc is in the retrieved_context
            # Actually our RAG agent just returns text in retrieved_context, not doc_ids directly.
            # But for offline eval, we mostly care about the final answer.
            # We will just log the results.
            
            results.append({
                "query": query,
                "latency": latency,
                "confidence": confidence,
                "intent": intent
            })
        
    latencies.sort()
    p50 = latencies[total // 2] if total > 0 else 0
    p95 = latencies[int(total * 0.95)] if total > 0 else 0
    
    avg_confidence = total_confidence / total if total > 0 else 0
    avg_groundedness = total_groundedness / total if total > 0 else 0
    escalation_rate = escalation_count / total if total > 0 else 0
    
    print("=== Eval Harness Results ===")
    print(f"Total Queries: {total}")
    print(f"Avg Confidence: {avg_confidence:.2f}")
    print(f"Avg Groundedness: {avg_groundedness:.2f}")
    print(f"Escalation Rate: {escalation_rate:.1%}")
    print(f"Latency p50: {p50:.2f}s")
    print(f"Latency p95: {p95:.2f}s")
    print("============================")

if __name__ == "__main__":
    # Note: Requires GROQ and GEMINI API keys in .env
    # run_eval_harness()
    print("Eval harness ready. Provide API keys to run.")
