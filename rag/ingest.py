"""
ingest.py -- Document Ingestion Pipeline

Reads text documents, splits them into chunks, creates embeddings,
and stores them in ChromaDB for retrieval.

Usage:
    # As a module:
    from rag.ingest import ingest_document
    ingest_document("path/to/doc.txt", persona_id=1, title="Lecture Notes")

    # As a script (ingest all sample docs):
    python -m rag.ingest
"""

import os
import re
import uuid
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

# Add project root to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.logger import logger


# === ChromaDB Configuration ===
# Data is stored locally in the rag/chroma_data directory
CHROMA_DIR = Path(__file__).parent / "chroma_data"
CHROMA_DIR.mkdir(exist_ok=True)

# Create a persistent ChromaDB client
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# Collection name — one collection for all personas
# We filter by persona_id in the metadata at query time
COLLECTION_NAME = "resonant_knowledge"


def get_collection():
    """Get or create the ChromaDB collection."""
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # Use cosine similarity
    )


# === Text Chunking ===

def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """
    Split text into overlapping chunks.

    We chunk by sentences to avoid cutting words or thoughts in half.
    Each chunk targets ~500 characters with 50 char overlap so
    context from one chunk flows into the next.

    Args:
        text: The full document text
        chunk_size: Target characters per chunk
        chunk_overlap: Characters of overlap between consecutive chunks

    Returns:
        List of text chunks
    """
    # Split by sentences (period, question mark, exclamation, or double newline)
    sentences = re.split(r'(?<=[.!?])\s+|\n\n+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # If adding this sentence would exceed the chunk size
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())

            # Start next chunk with overlap from the end of current chunk
            overlap_text = current_chunk[-chunk_overlap:] if chunk_overlap > 0 else ""
            current_chunk = overlap_text + " " + sentence
        else:
            current_chunk += (" " + sentence if current_chunk else sentence)

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# === Document Ingestion ===

def ingest_document(
    file_path: str,
    persona_id: int,
    title: Optional[str] = None,
    chunk_size: int = 500,
) -> dict:
    """
    Ingest a text document into ChromaDB.

    Steps:
        1. Read the document text
        2. Split into chunks
        3. Add each chunk to ChromaDB with metadata
           (ChromaDB auto-generates embeddings using its default model)

    Args:
        file_path: Path to the text file
        persona_id: Which persona this document belongs to
        title: Document title (defaults to filename)
        chunk_size: Target characters per chunk

    Returns:
        dict with ingestion stats
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    title = title or file_path.stem.replace("_", " ").title()

    # Read the document
    text = file_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"Document is empty: {file_path}")

    logger.info(f"Ingesting document: '{title}' ({len(text)} chars) for persona {persona_id}")

    # Chunk the text
    chunks = chunk_text(text, chunk_size=chunk_size)
    logger.info(f"  Split into {len(chunks)} chunks (target: {chunk_size} chars each)")

    # Prepare data for ChromaDB
    collection = get_collection()

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"p{persona_id}_{file_path.stem}_{i}_{uuid.uuid4().hex[:6]}"
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "persona_id": persona_id,
            "title": title,
            "source_file": str(file_path.name),
            "chunk_index": i,
            "total_chunks": len(chunks),
        })

    # Add to ChromaDB (embeddings are auto-generated)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info(f"  Ingested {len(chunks)} chunks into ChromaDB collection '{COLLECTION_NAME}'")

    return {
        "title": title,
        "persona_id": persona_id,
        "file": str(file_path.name),
        "total_chars": len(text),
        "chunk_count": len(chunks),
        "chunk_size": chunk_size,
    }


def ingest_directory(
    directory: str,
    persona_id: int,
    chunk_size: int = 500,
) -> list[dict]:
    """Ingest all .txt files from a directory."""
    dir_path = Path(directory)
    results = []

    for txt_file in sorted(dir_path.glob("*.txt")):
        result = ingest_document(str(txt_file), persona_id, chunk_size=chunk_size)
        results.append(result)

    return results


def delete_persona_documents(persona_id: int) -> int:
    """Delete all chunks belonging to a specific persona."""
    collection = get_collection()

    # Get all chunks for this persona
    results = collection.get(
        where={"persona_id": persona_id},
    )

    if results["ids"]:
        collection.delete(ids=results["ids"])
        logger.info(f"Deleted {len(results['ids'])} chunks for persona {persona_id}")
        return len(results["ids"])

    return 0


def get_collection_stats() -> dict:
    """Get statistics about the ChromaDB collection."""
    collection = get_collection()
    count = collection.count()
    return {
        "collection": COLLECTION_NAME,
        "total_chunks": count,
        "storage_path": str(CHROMA_DIR),
    }


# === CLI Entry Point ===

if __name__ == "__main__":
    """Ingest all sample documents for persona 1 (Dr. Ayesha Sharma)."""
    sample_dir = Path(__file__).parent / "sample_docs"

    print("Resonant RAG Ingestion")
    print("=" * 40)

    if not list(sample_dir.glob("*.txt")):
        print(f"No .txt files found in {sample_dir}")
        sys.exit(1)

    results = ingest_directory(str(sample_dir), persona_id=1)

    print()
    for r in results:
        print(f"  [OK] {r['title']}: {r['chunk_count']} chunks ({r['total_chars']} chars)")

    print()
    stats = get_collection_stats()
    print(f"Total chunks in database: {stats['total_chunks']}")
    print(f"Storage: {stats['storage_path']}")
    print()
    print("Done! Documents are ready for RAG retrieval.")
