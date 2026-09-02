"""
test_llm.py -- Tests for LLM Service, Prompt Loader, and Pipeline Integration

Run with:
    pytest backend/tests/test_llm.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ==========================================
# Prompt Loader Tests
# ==========================================

class TestPromptLoader:
    """Tests for the prompt loading and compilation system."""

    def _make_persona(self):
        """Create a mock persona object for testing."""

        class MockPersona:
            name = "Dr. Ayesha Sharma"
            role = "Professor of Computer Science"
            institution = "IIT Delhi"
            personality_traits = ["Patient", "Uses real-world analogies", "Humorous"]
            knowledge_areas = ["Machine Learning", "Cloud Computing"]
            speaking_style = "Conversational but academic"
            constraints = ["Never claim to be human", "Keep responses under 150 words"]
            voice_sample_path = None
            system_prompt = None

        return MockPersona()

    def test_build_prompt_basic(self):
        """Should compile a prompt with persona data."""
        from backend.prompts.prompt_loader import build_system_prompt

        persona = self._make_persona()
        prompt = build_system_prompt(persona, target_language="en")

        assert "Dr. Ayesha Sharma" in prompt
        assert "Professor of Computer Science" in prompt
        assert "IIT Delhi" in prompt
        assert "Machine Learning" in prompt
        assert "English" in prompt

    def test_build_prompt_includes_constraints(self):
        """Should include both default and persona-specific constraints."""
        from backend.prompts.prompt_loader import build_system_prompt

        persona = self._make_persona()
        prompt = build_system_prompt(persona, target_language="en")

        # Default constraint
        assert "Never claim to be a real human" in prompt
        # Persona-specific constraint
        assert "Keep responses under 150 words" in prompt

    def test_build_prompt_with_context(self):
        """Should include RAG context chunks when provided."""
        from backend.prompts.prompt_loader import build_system_prompt

        persona = self._make_persona()
        context = ["ML uses neural networks.", "Cloud runs on AWS."]
        prompt = build_system_prompt(persona, context_chunks=context)

        assert "ML uses neural networks" in prompt
        assert "Cloud runs on AWS" in prompt

    def test_build_prompt_hindi(self):
        """Should use 'Hindi' as language name for code 'hi'."""
        from backend.prompts.prompt_loader import build_system_prompt

        persona = self._make_persona()
        prompt = build_system_prompt(persona, target_language="hi")

        assert "Hindi" in prompt

    def test_build_prompt_includes_watermark(self):
        """Should include the AI watermark instruction."""
        from backend.prompts.prompt_loader import build_system_prompt

        persona = self._make_persona()
        prompt = build_system_prompt(persona)

        assert "AI-Generated Response" in prompt
        assert "Digital Twin" in prompt

    def test_language_name_mapping(self):
        """Should map language codes to readable names."""
        from backend.prompts.prompt_loader import get_language_name

        assert get_language_name("en") == "English"
        assert get_language_name("hi") == "Hindi"
        assert get_language_name("es") == "Spanish"
        assert get_language_name("xx") == "XX"  # Unknown code returns uppercase


# ==========================================
# LLM Service Tests
# ==========================================

class TestLLMService:
    """Tests for the LLM service."""

    def test_fallback_when_ollama_offline(self):
        """Should return fallback response when Ollama is not reachable."""
        from backend.services.llm_service import llm_service

        result = llm_service.generate(
            system_prompt="You are Dr. Sharma.",
            user_message="What is machine learning?",
        )

        # Since Ollama is not running locally during tests,
        # it should fall back gracefully
        assert result["reply"], "Reply should not be empty"
        assert result["mode"] in ("ollama", "fallback")
        assert result["duration_ms"] >= 0

    def test_fallback_contains_user_message(self):
        """Fallback response should echo the user's message."""
        from backend.services.llm_service import llm_service

        # Force fallback by checking availability first
        result = llm_service._generate_fallback(
            system_prompt="You are a professor.",
            user_message="Explain neural networks",
        )

        assert "Explain neural networks" in result["reply"]
        assert result["mode"] == "fallback"

    def test_is_available_returns_bool(self):
        """is_available should return True or False without crashing."""
        from backend.services.llm_service import llm_service

        result = llm_service.is_available()
        assert isinstance(result, bool)


# ==========================================
# Pipeline Integration Test
# ==========================================

class TestPipelineWithLLM:
    """Test the full pipeline with STT + LLM (fallback mode)."""

    @pytest.fixture(scope="class")
    def test_audio_bytes(self):
        """Generate test audio bytes."""
        from gtts import gTTS
        import io

        buffer = io.BytesIO()
        tts = gTTS("What is deep learning?", lang="en")
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()

    def test_full_pipeline_stt_plus_llm(self, test_audio_bytes):
        """
        Upload audio -> get real transcript + LLM reply.
        LLM will be in fallback mode since Ollama isn't running in tests.
        """
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/api/process",
            files={"audio": ("test.mp3", test_audio_bytes, "audio/mpeg")},
            data={"target_language": "en", "persona_id": "1"},
        )

        assert response.status_code == 200
        data = response.json()

        # STT should return real transcript
        assert len(data["transcript"]) > 0
        assert "[STT not connected yet]" not in data["transcript"]

        # LLM should return something (either real or fallback)
        assert len(data["reply_text"]) > 0
        assert "[LLM not connected yet]" not in data["reply_text"]

        # Processing time should be recorded
        assert data["processing_time_ms"] > 0

    def test_pipeline_with_invalid_persona(self, test_audio_bytes):
        """Should handle non-existent persona gracefully."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/api/process",
            files={"audio": ("test.mp3", test_audio_bytes, "audio/mpeg")},
            data={"target_language": "en", "persona_id": "9999"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "not found" in data["reply_text"].lower()
