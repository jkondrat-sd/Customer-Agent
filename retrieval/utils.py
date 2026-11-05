"""Shared utilities for the retrieval pipeline."""

import re

def tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercasing tokenizer for BM25.
    
    Used consistently across ingestion and retrieval to ensure sparse search
    matches the index perfectly.
    """
    return re.sub(r"[^\w\s]", "", text.lower()).split()
