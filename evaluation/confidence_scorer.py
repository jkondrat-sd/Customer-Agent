from typing import List

def check_groundedness(answer: str, retrieved_context: List[str]) -> float:
    """
    Checks if key terms in the answer are present in the context.
    A very simple proxy for groundedness: token overlap.
    In a real system, this could be an LLM-as-a-judge call.
    """
    if not retrieved_context:
        return 0.0
        
    combined_context = " ".join(retrieved_context).lower()
    answer_tokens = set(word.lower() for word in answer.split() if len(word) > 3)
    
    if not answer_tokens:
        return 1.0 # Trivial/short answer
        
    overlap_count = sum(1 for token in answer_tokens if token in combined_context)
    return overlap_count / len(answer_tokens)

def compute_unified_confidence(
    retrieval_score: float, 
    llm_confidence: float, 
    answer: str, 
    retrieved_context: List[str]
) -> float:
    """
    Combines retrieval score, LLM confidence, and groundedness into a single score.
    Weights are tuned empirically.
    """
    groundedness = check_groundedness(answer, retrieved_context)
    
    # Weights for the final score
    W_RETRIEVAL = 0.3
    W_LLM = 0.3
    W_GROUNDEDNESS = 0.4
    
    final_score = (
        (retrieval_score * W_RETRIEVAL) + 
        (llm_confidence * W_LLM) + 
        (groundedness * W_GROUNDEDNESS)
    )
    
    return final_score
