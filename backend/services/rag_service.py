"""
rag_service.py -- RAG Retrieval Service

Retrieves the most relevant document chunks from ChromaDB
for a given user query and persona.

This is Stage 3 of the pipeline:
    User question → find relevant docs → inject into LLM prompt

Usage:
    from backend.services.rag_service import rag_service

    chunks = rag_service.retrieve("What is on the final exam?", persona_id=1)
    # chunks = [
    #     "The final exam covers chapters 5 through 10...",
    #     "Focus on ML algorithms and their complexity...",
    # ]
"""

from typing import Optional

from rag.ingest import get_collection
from backend.utils.logger import logger


class RAGService:
    """
    Retrieval-Augmented Generation service.

    Searches ChromaDB for document chunks that are semantically
    similar to the user's question, filtered by persona_id.
    """

    # How many chunks to retrieve per query
    DEFAULT_N_RESULTS = 3

    # Minimum similarity score (0-1, lower = more similar in cosine distance)
    # Chunks with distance > this threshold are too irrelevant to include
    MAX_DISTANCE = 1.0

    def retrieve(
        self,
        query: str,
        persona_id: int,
        n_results: int = DEFAULT_N_RESULTS,
    ) -> list[str]:
        """
        Retrieve relevant document chunks for a query.

        Args:
            query: The user's question (transcribed text)
            persona_id: Which persona's documents to search
            n_results: Maximum number of chunks to return

        Returns:
            List of relevant text chunks, ordered by relevance.
            Returns empty list if no relevant documents found.
        """
        if not query or not query.strip():
            return []

        collection = get_collection()

        # Check if there are any documents for this persona
        if collection.count() == 0:
            logger.debug("ChromaDB collection is empty — no documents ingested yet")
            return []

        try:
            # Query ChromaDB — it automatically embeds the query
            # and finds the most similar document chunks
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"persona_id": persona_id},
            )

            # Extract chunks and their distances
            chunks = []
            if results and results["documents"] and results["documents"][0]:
                documents = results["documents"][0]
                distances = results["distances"][0] if results["distances"] else []
                metadatas = results["metadatas"][0] if results["metadatas"] else []

                for i, doc in enumerate(documents):
                    distance = distances[i] if i < len(distances) else 0
                    metadata = metadatas[i] if i < len(metadatas) else {}

                    # Filter out chunks that are too dissimilar
                    if distance <= self.MAX_DISTANCE:
                        chunks.append(doc)
                        logger.debug(
                            f"  RAG chunk {i+1}: distance={distance:.3f}, "
                            f"source='{metadata.get('title', 'unknown')}' "
                            f"(chunk {metadata.get('chunk_index', '?')}/{metadata.get('total_chunks', '?')})"
                        )

            if chunks:
                logger.info(
                    f"RAG retrieved {len(chunks)} chunks for persona {persona_id} "
                    f"(query: '{query[:50]}...')" if len(query) > 50 else
                    f"RAG retrieved {len(chunks)} chunks for persona {persona_id} "
                    f"(query: '{query}')"
                )
            else:
                logger.debug(f"RAG found no relevant chunks for persona {persona_id}")

            return chunks

        except Exception as e:
            logger.error(f"RAG retrieval failed: {str(e)}")
            return []  # Graceful degradation — pipeline continues without context

    def has_documents(self, persona_id: int) -> bool:
        """Check if a persona has any ingested documents."""
        collection = get_collection()
        try:
            results = collection.get(
                where={"persona_id": persona_id},
                limit=1,
            )
            return len(results["ids"]) > 0
        except Exception:
            return False


# Global singleton
rag_service = RAGService()
