# app/vectorstore/pinecone_ops.py
"""
Pinecone helpers for Lumora
───────────────────────────
• create (or fetch) a serverless index named via PINECONE_INDEX_NAME  
• embed chunks with OpenAI `text-embedding-3-small` (1536-dim)  
• upsert in batches, 1 namespace == 1 document_id
"""
from __future__ import annotations

import itertools
import os
import uuid
from functools import lru_cache
from typing import Iterable, Dict, Any

from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec, CloudProvider

# ── config ────────────────────────────────────────────────────────────────────
PINECONE_API_KEY     = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "aws-us-east-1")  # gcp-starter, etc.
PINECONE_INDEX_NAME  = os.getenv("PINECONE_INDEX_NAME", "lumora")
EMBED_MODEL          = "text-embedding-3-small"
BATCH_SIZE           = 100                    # 100 texts ≈ 30 k tokens → safe for embed endpoint


# ── Application-level singletons ────────────────────────────────────────────────
# Global variables to store initialized components
_PINECONE_CLIENT = None
_PINECONE_INDEX = None
_EMBEDDER = None

def _get_pc():
    global _PINECONE_CLIENT
    if _PINECONE_CLIENT is None:
        if not PINECONE_API_KEY:
            raise RuntimeError("PINECONE_API_KEY not set")
        _PINECONE_CLIENT = Pinecone(api_key=PINECONE_API_KEY)
    return _PINECONE_CLIENT

def get_index():
    global _PINECONE_INDEX
    if _PINECONE_INDEX is None:
        # This should only happen if init_pinecone() wasn't called at startup
        init_pinecone()
    return _PINECONE_INDEX

def get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = OpenAIEmbeddings(model=EMBED_MODEL)  # uses OPENAI_API_KEY from env
    return _EMBEDDER

def init_pinecone():
    """Initialize Pinecone client and index at application startup"""
    global _PINECONE_CLIENT, _PINECONE_INDEX
    
    # Initialize Pinecone client
    pc = _get_pc()
    
    # Check if index exists
    if PINECONE_INDEX_NAME not in [idx.name for idx in pc.list_indexes()]:
        # Create index if it doesn't exist
        index_config = pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(cloud=CloudProvider.AWS, region="us-east-1"),
        )
        # Wait for index to be ready
        pc.describe_index(PINECONE_INDEX_NAME)
    else:
        # Get existing index info
        index_config = pc.describe_index(PINECONE_INDEX_NAME)
        
    # Connect to the index
    _PINECONE_INDEX = pc.Index(name=PINECONE_INDEX_NAME)


# ── public API ────────────────────────────────────────────────────────────────
def upsert_text_chunks(
    *,
    document_id: uuid.UUID,
    chunks: Iterable[Dict[str, Any]],
) -> None:
    """
    Embed & upsert **text** chunks into Pinecone.
    • Non-text items are skipped.
    • Each vector id:  <doc_id>_<page>_<8-char-uuid>
    • Namespace:       str(document_id)
    Metadata saved:    page(int), text(str[:200]) for quick view
    """
    index = get_index()
    embedder = get_embedder()

    texts, meta, ids = [], [], []

    for ch in chunks:
        text = ch.get("text") or ch.get("text_content")  # adapt to result dict
        if not text:
            continue

        page = ch.get("page", ch.get("page_number", 0)) + 1
        vec_id = f"{document_id}_{page}_{uuid.uuid4().hex[:8]}"
        
        # Extract enhanced metadata if available
        metadata = {
            "page": page,
            "snippet": ch.get("snippet", text[:300]),  # Use pre-computed snippet if available, or create one
        }
        
        # Include heading information if available for better context
        if ch.get("headings"):
            metadata["headings"] = ch.get("headings")
            
        # Include document structure metadata if available
        if ch.get("metadata"):
            chunk_metadata = ch.get("metadata")
            if chunk_metadata.get("chunk_index") is not None:
                metadata["chunk_index"] = chunk_metadata.get("chunk_index")
            if chunk_metadata.get("total_chunks") is not None:
                metadata["total_chunks"] = chunk_metadata.get("total_chunks")

        texts.append(text)
        meta.append(metadata)
        ids.append(vec_id)

        # embed & push in batches
        if len(texts) >= BATCH_SIZE:
            _push_batch(index, embedder, ids, texts, meta, document_id)
            texts, meta, ids = [], [], []

    # push remainder
    if texts:
        _push_batch(index, embedder, ids, texts, meta, document_id)


# ── internal helpers ─────────────────────────────────────────────────────────
def _push_batch(index, embedder, ids, texts, meta, document_id):
    vectors = embedder.embed_documents(texts)
    payload = [
        {"id": i, "values": vec, "metadata": m}
        for i, vec, m in zip(ids, vectors, meta)
    ]
    index.upsert(vectors=payload, namespace=str(document_id))
