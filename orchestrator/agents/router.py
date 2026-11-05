from langchain_groq import ChatGroq
from orchestrator.state import SupportState
from orchestrator.models import IntentClassification

def route_intent(state: SupportState) -> SupportState:
    """
    Classifies the user's intent into 'faq', 'action', or 'complex'.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "faq"}
    
    # Use Groq for fast intent routing
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    structured_llm = llm.with_structured_output(IntentClassification)
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Extract the last message text
    last_message = messages[-1]
    query = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    prompt = f"""
    You are a customer support router. Classify the intent of the following user query.
    - 'faq': The user is asking a general question about policies, troubleshooting, or knowledge base info.
    - 'action': The user wants to perform a specific action like checking order status, getting a refund, or managing their account.
    - 'complex': The user is frustrated, angry, or has a complex issue that requires human intervention.
    - 'proactive_delay': The system proactively notifying the customer about a delivery delay (triggered by Kafka event).
    - 'out_of_scope': The user is asking for something completely unrelated to customer support (e.g., writing code, general knowledge questions, jokes).
    
    User query: {query}
    """
    
    logger.info("route_intent: Starting Groq invocation")
    try:
        response = structured_llm.invoke(prompt)
        logger.info(f"route_intent: Groq invocation finished, response={response}")
    except Exception as e:
        logger.error(f"route_intent: Groq invocation failed with error: {e}")
        raise
    
    intent = response.intent if response and hasattr(response, "intent") else "faq"
    
    # Ensure intent is valid
    if intent not in ["faq", "action", "complex", "proactive_delay", "out_of_scope"]:
        intent = "faq"
        
    return {"intent": intent}
