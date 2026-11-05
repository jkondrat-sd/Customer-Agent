"""Document ingestion pipeline.

Loads enterprise docs (Markdown/text), chunks them, embeds via Gemini,
upserts to Pinecone, and builds a parallel BM25 index on disk.

Architecture rule (skill.md §1): Both dense and sparse indices are built
from the *same* chunk corpus so hybrid search operates over identical
document IDs.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from pathlib import Path
from typing import TypedDict

from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

from retrieval.utils import tokenize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class Chunk(TypedDict):
    """A single text chunk with provenance metadata."""

    chunk_id: str
    doc_id: str
    text: str
    source: str  # original filename


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_markdown(path: Path) -> str:
    """Read a Markdown/text file and return its raw content."""
    return path.read_text(encoding="utf-8")


def load_documents(docs_dir: str | Path) -> list[dict[str, str]]:
    """Load all supported documents from *docs_dir*.

    Returns a list of ``{doc_id, source, text}`` dicts.
    Currently supports ``.md`` and ``.txt`` files.
    """
    docs_dir = Path(docs_dir)
    documents: list[dict[str, str]] = []

    supported_extensions = {".md", ".txt"}
    for path in sorted(docs_dir.iterdir()):
        if path.suffix.lower() not in supported_extensions:
            logger.debug("Skipping unsupported file: %s", path.name)
            continue

        text = _load_markdown(path)
        # Deterministic doc_id from filename so re-ingestion is idempotent.
        doc_id = hashlib.sha256(path.name.encode()).hexdigest()[:16]
        documents.append({"doc_id": doc_id, "source": path.name, "text": text})
        logger.info("Loaded %s (%d chars)", path.name, len(text))

    if not documents:
        logger.warning("No documents found in %s", docs_dir)
    return documents


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_documents(
    documents: list[dict[str, str]],
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """Split documents into overlapping chunks.

    Uses ``RecursiveCharacterTextSplitter`` (LangChain) with Markdown-aware
    separators for better boundary selection.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
        keep_separator=True,
    )

    chunks: list[Chunk] = []
    for doc in documents:
        splits = splitter.split_text(doc["text"])
        for i, text in enumerate(splits):
            chunk_id = f"{doc['doc_id']}_chunk_{i}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc["doc_id"],
                    text=text,
                    source=doc["source"],
                )
            )
    logger.info("Created %d chunks from %d documents", len(chunks), len(documents))
    return chunks


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _embed_texts(texts: list[str], api_key: str, model: str) -> list[list[float]]:
    """Embed a batch of texts using the Gemini embedding model.

    Calls ``langchain_google_genai.GoogleGenerativeAIEmbeddings`` so we get
    automatic batching and retry logic from LangChain.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embedder = GoogleGenerativeAIEmbeddings(
        model=model,
        google_api_key=api_key,
    )
    return embedder.embed_documents(texts)


# ---------------------------------------------------------------------------
# Pinecone upsert
# ---------------------------------------------------------------------------

def upsert_to_pinecone(
    chunks: list[Chunk],
    *,
    api_key: str,
    index_name: str,
    embedding_api_key: str,
    embedding_model: str,
    batch_size: int = 100,
) -> int:
    """Embed chunks and upsert them into a Pinecone index.

    Returns the number of vectors upserted.
    """
    from pinecone import Pinecone

    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)

    total_upserted = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = _embed_texts(texts, api_key=embedding_api_key, model=embedding_model)

        vectors = [
            {
                "id": chunk["chunk_id"],
                "values": emb,
                "metadata": {
                    "doc_id": chunk["doc_id"],
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "source": chunk["source"],
                },
            }
            for chunk, emb in zip(batch, embeddings)
        ]
        index.upsert(vectors=vectors)
        total_upserted += len(vectors)
        logger.info(
            "Upserted batch %d–%d (%d vectors)",
            start,
            start + len(batch),
            len(vectors),
        )
        if start + batch_size < len(chunks):
            import time
            logger.info("Sleeping for 40 seconds to respect Gemini API rate limits...")
            time.sleep(40)

    logger.info("Total vectors upserted: %d", total_upserted)
    return total_upserted


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------


def build_bm25_index(
    chunks: list[Chunk],
    output_path: str | Path,
) -> BM25Okapi:
    """Build a BM25 index over chunk texts and persist to disk.

    The pickle file stores ``(bm25_model, chunk_ids, chunk_texts)`` so the
    retriever can map scores back to chunk identifiers.
    """
    corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus)

    payload = {
        "bm25": bm25,
        "chunk_ids": [c["chunk_id"] for c in chunks],
        "chunk_texts": [c["text"] for c in chunks],
        "chunk_sources": [c["source"] for c in chunks],
        "chunk_doc_ids": [c["doc_id"] for c in chunks],
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(payload, f)

    logger.info("BM25 index saved to %s (%d documents)", output_path, len(chunks))
    return bm25


# ---------------------------------------------------------------------------
# Full ingestion pipeline
# ---------------------------------------------------------------------------

def run_ingestion(
    docs_dir: str | Path | None = None,
    *,
    pinecone_api_key: str | None = None,
    pinecone_index_name: str | None = None,
    embedding_api_key: str | None = None,
    embedding_model: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    bm25_output_path: str | Path | None = None,
    skip_pinecone: bool = False,
) -> list[Chunk]:
    """Run the full ingestion pipeline: load → chunk → embed → store.

    Parameters fall back to ``config.settings`` when not provided explicitly,
    keeping the function usable both programmatically and from the CLI.
    """
    from config import settings

    docs_dir = docs_dir or settings.docs_dir
    pinecone_api_key = pinecone_api_key or settings.pinecone_api_key
    pinecone_index_name = pinecone_index_name or settings.pinecone_index_name
    embedding_api_key = embedding_api_key or settings.gemini_api_key
    embedding_model = embedding_model or settings.embedding_model
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap
    bm25_output_path = bm25_output_path or settings.bm25_index_path

    # 1. Load
    documents = load_documents(docs_dir)
    logger.info("Loaded %d documents from %s", len(documents), docs_dir)

    # 2. Chunk
    chunks = chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # 3. Dense index (Pinecone)
    if not skip_pinecone:
        upsert_to_pinecone(
            chunks,
            api_key=pinecone_api_key,
            index_name=pinecone_index_name,
            embedding_api_key=embedding_api_key,
            embedding_model=embedding_model,
        )
    else:
        logger.info("Skipping Pinecone upsert (skip_pinecone=True)")

    # 4. Sparse index (BM25)
    build_bm25_index(chunks, bm25_output_path)

    logger.info("Ingestion complete: %d chunks indexed", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    run_ingestion()
