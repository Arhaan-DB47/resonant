"""
test_rag.py -- Tests for RAG Pipeline (Ingestion + Retrieval)

Run with:
    pytest backend/tests/test_rag.py -v
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ==========================================
# Text Chunking Tests
# ==========================================

class TestChunking:
    """Tests for the text chunking function."""

    def test_basic_chunking(self):
        """Should split text into chunks."""
        from rag.ingest import chunk_text

        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        chunks = chunk_text(text, chunk_size=50, chunk_overlap=0)

        assert len(chunks) >= 2
        assert all(len(c) > 0 for c in chunks)

    def test_chunk_size_respected(self):
        """Chunks should be approximately the target size."""
        from rag.ingest import chunk_text

        text = ". ".join([f"This is sentence number {i}" for i in range(50)])
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=0)

        # Most chunks should be under 250 chars (some leeway for sentence boundaries)
        for chunk in chunks[:-1]:  # Last chunk can be shorter
            assert len(chunk) < 350, f"Chunk too large: {len(chunk)} chars"

    def test_no_empty_chunks(self):
        """Should not produce empty chunks."""
        from rag.ingest import chunk_text

        text = "Hello world. This is a test. Another sentence here."
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=0)

        assert all(c.strip() for c in chunks)

    def test_single_sentence(self):
        """A single sentence should produce one chunk."""
        from rag.ingest import chunk_text

        text = "Just one sentence here."
        chunks = chunk_text(text, chunk_size=500)

        assert len(chunks) == 1
        assert "one sentence" in chunks[0]


# ==========================================
# Ingestion Tests
# ==========================================

class TestIngestion:
    """Tests for document ingestion into ChromaDB."""

    def _create_temp_doc(self, content: str) -> str:
        """Helper to create a temp text file."""
        path = os.path.join(tempfile.gettempdir(), f"resonant_test_doc_{os.getpid()}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_ingest_document(self):
        """Should ingest a document and return stats."""
        from rag.ingest import ingest_document, delete_persona_documents

        # Use a unique persona_id to avoid conflicts
        test_persona_id = 9990

        path = self._create_temp_doc(
            "Machine learning is great. "
            "Neural networks are powerful. "
            "Deep learning uses many layers. "
            "Training requires data and compute."
        )

        try:
            result = ingest_document(path, persona_id=test_persona_id, title="Test Doc")

            assert result["title"] == "Test Doc"
            assert result["persona_id"] == test_persona_id
            assert result["chunk_count"] >= 1
            assert result["total_chars"] > 0
        finally:
            delete_persona_documents(test_persona_id)
            os.remove(path)

    def test_ingest_nonexistent_file(self):
        """Should raise FileNotFoundError."""
        from rag.ingest import ingest_document

        with pytest.raises(FileNotFoundError):
            ingest_document("/nonexistent/file.txt", persona_id=9991)

    def test_ingest_empty_file(self):
        """Should raise ValueError for empty files."""
        from rag.ingest import ingest_document

        path = self._create_temp_doc("")
        try:
            with pytest.raises(ValueError, match="empty"):
                ingest_document(path, persona_id=9992)
        finally:
            os.remove(path)


# ==========================================
# RAG Retrieval Tests
# ==========================================

class TestRAGRetrieval:
    """Tests for the RAG retrieval service."""

    @pytest.fixture(scope="class", autouse=True)
    def ingest_test_docs(self):
        """Ingest sample docs before tests, clean up after."""
        from rag.ingest import ingest_document, delete_persona_documents

        test_persona_id = 9995

        # Create and ingest a test document
        path = os.path.join(tempfile.gettempdir(), "resonant_rag_test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "The final exam covers chapters 5 through 10 of the course material. "
                "The exam is open book and 3 hours duration. "
                "Focus on machine learning algorithms and their computational complexity. "
                "Students may bring printed notes and textbooks. "
                "No electronic devices are allowed during the exam. "
                "Office hours are Tuesday and Thursday from 2 PM to 4 PM in Room 301."
            )

        ingest_document(path, persona_id=test_persona_id, title="Test Syllabus")

        yield test_persona_id

        # Cleanup
        delete_persona_documents(test_persona_id)
        if os.path.exists(path):
            os.remove(path)

    def test_retrieve_relevant_chunks(self, ingest_test_docs):
        """Should retrieve chunks relevant to the query."""
        from backend.services.rag_service import rag_service

        persona_id = ingest_test_docs
        chunks = rag_service.retrieve("What is on the final exam?", persona_id=persona_id)

        assert len(chunks) > 0, "Should retrieve at least one chunk"
        # The retrieved text should contain exam-related content
        combined = " ".join(chunks).lower()
        assert "exam" in combined or "chapter" in combined, (
            f"Retrieved chunks should mention exam info, got: {combined[:200]}"
        )

    def test_retrieve_no_results_for_wrong_persona(self, ingest_test_docs):
        """Should return empty list for a persona with no documents."""
        from backend.services.rag_service import rag_service

        chunks = rag_service.retrieve("What is on the exam?", persona_id=9999)
        assert chunks == []

    def test_retrieve_empty_query(self):
        """Should return empty list for empty query."""
        from backend.services.rag_service import rag_service

        chunks = rag_service.retrieve("", persona_id=1)
        assert chunks == []

    def test_has_documents(self, ingest_test_docs):
        """Should detect whether a persona has documents."""
        from backend.services.rag_service import rag_service

        persona_id = ingest_test_docs
        assert rag_service.has_documents(persona_id) is True
        assert rag_service.has_documents(9999) is False


# ==========================================
# Knowledge Upload API Tests
# ==========================================

class TestKnowledgeAPI:
    """Tests for the knowledge upload endpoint."""

    def test_upload_document(self):
        """Should upload a document and ingest it."""
        from fastapi.testclient import TestClient
        from backend.main import app
        from rag.ingest import delete_persona_documents

        client = TestClient(app)

        doc_content = (
            "Python is a programming language. "
            "It is widely used in data science and machine learning. "
            "Python has libraries like NumPy, Pandas, and Scikit-learn."
        )

        try:
            response = client.post(
                "/api/personas/1/knowledge",
                files={"document": ("test_doc.txt", doc_content.encode(), "text/plain")},
                data={"title": "Python Notes"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["title"] == "Python Notes"
            assert data["chunk_count"] >= 1
            assert "ingested successfully" in data["message"]
        finally:
            delete_persona_documents(1)

    def test_upload_to_nonexistent_persona(self):
        """Should return 404 for non-existent persona."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/api/personas/9999/knowledge",
            files={"document": ("test.txt", b"Some content", "text/plain")},
        )

        assert response.status_code == 404

    def test_list_knowledge_documents(self):
        """Should list documents for a persona."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.get("/api/personas/1/knowledge")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total_documents" in data
