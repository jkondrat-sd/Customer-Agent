from pydantic import BaseModel, Field

class IntentClassification(BaseModel):
    intent: str = Field(
        description="The intent of the user's query. Must be one of: 'faq', 'action', 'complex', 'proactive_delay', or 'out_of_scope'."
    )

class RAGResponse(BaseModel):
    answer: str = Field(description="The answer to the user's question based ONLY on the context. If the context does not contain the answer, say 'I don't know'.")
    confidence: float | str = Field(description="Confidence score between 0.0 and 1.0 that the answer fully resolves the query using the context. Important: Output as a raw number (e.g., 0.0 or 1.0), not a string.")

class ActionResponse(BaseModel):
    """Structured output for the action agent (skill.md §4)."""
    answer: str = Field(description="A clear, actionable response to the user's account/order request. Provide step-by-step instructions when applicable.")
    confidence: float | str = Field(description="Confidence score between 0.0 and 1.0 that the response fully addresses the user's action request. Important: Output as a raw number (e.g., 0.0 or 1.0), not a string.")
    action_type: str = Field(description="The type of action: 'password_reset', 'order_status', 'refund', 'account_management', or 'other'.")

