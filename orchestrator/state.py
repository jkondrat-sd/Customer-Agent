from typing import TypedDict, Annotated
import operator

class SupportState(TypedDict):
    messages: Annotated[list, operator.add]
    intent: str
    retrieved_context: list
    retrieved_chunks: list
    confidence: float
    retry_count: int
