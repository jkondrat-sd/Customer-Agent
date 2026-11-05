"""Centralized configuration loaded from environment variables.

All secrets and tunables come from .env (local) or GCP Secret Manager (prod).
Never hardcode API keys or DB URLs — see skill.md rule 7.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")


class Settings(BaseModel):
    """Application-wide settings. All values sourced from environment."""

    # --- API keys (never committed) ---
    cohere_api_key: str = os.getenv("COHERE_API_KEY") or ""
    gemini_api_key: str = os.getenv("GEMINI_API_KEY") or ""
    groq_api_key: str = os.getenv("GROQ_API_KEY") or ""
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY") or ""
    pinecone_env: str = os.getenv("PINECONE_ENV") or ""

    # --- Pinecone ---
    pinecone_index_name: str = os.getenv("PINECONE_INDEX_NAME") or "support-docs"

    # --- Database ---
    database_url: str = (os.getenv("DATABASE_URL") or "sqlite:///./support_platform.db").strip()

    # --- Embedding ---
    embedding_model: str = os.getenv("EMBEDDING_MODEL") or "models/gemini-embedding-2"
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION") or "768")

    # --- Retrieval ---
    chunk_size: int = int(os.getenv("CHUNK_SIZE") or "400")
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP") or "50")
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K") or "20")
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N") or "5")

    # --- Paths ---
    bm25_index_path: str = os.getenv("BM25_INDEX_PATH") or "bm25_index.pkl"
    docs_dir: str = os.getenv("DOCS_DIR") or "docs"


settings = Settings()
