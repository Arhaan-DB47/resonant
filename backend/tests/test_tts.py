"""
test_tts.py -- Tests for the TTS Service and Full Pipeline

Run with:
    pytest backend/tests/test_tts.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.tts_service import tts_service


# ==========================================
# TTS Service Tests
# ==========================================

class TestTTSService:
    """Tests for the TTS service (gTTS mode)."""

    def test_synthesize_english(self):
        """Should generate an MP3 file from English text."""
        result = tts_service.synthesize("Hello, this is a test.", language="en")

        assert result["audio_path"].startswith("/outputs/")
        assert result["audio_path"].endswith(".mp3")
        assert result["mode"] == "gtts"
        assert result["duration_ms"] > 0
        assert os.path.exists(result["audio_file"])
        assert os.path.getsize(result["audio_file"]) > 0

    def test_synthesize_hindi(self):
        """Should generate audio in Hindi."""
        result = tts_service.synthesize("यह एक परीक्षा है।", language="hi")

        assert result["audio_path"].endswith(".mp3")
        assert result["mode"] == "gtts"
        assert os.path.exists(result["audio_file"])

    def test_synthesize_strips_watermark(self):
        """Should remove [AI-Generated Response] brackets before speaking."""
        text = "Machine learning is great. [AI-Generated Response — Digital Twin of Dr. Sharma]"
        result = tts_service.synthesize(text, language="en")

        # Should succeed (gTTS would fail on weird bracket text)
        assert result["mode"] == "gtts"
        assert os.path.exists(result["audio_file"])

    def test_synthesize_strips_markdown(self):
        """Should remove markdown formatting before speaking."""
        text = "## Heading\n\n**Bold text** and *italic text*\n\nParagraph two."
        result = tts_service.synthesize(text, language="en")

        assert result["mode"] == "gtts"
        assert os.path.exists(result["audio_file"])

    def test_synthesize_rejects_empty_text(self):
        """Should raise ValueError for empty text."""
        with pytest.raises(ValueError, match="empty"):
            tts_service.synthesize("", language="en")

    def test_synthesize_rejects_whitespace_only(self):
        """Should raise ValueError for whitespace-only text."""
        with pytest.raises(ValueError, match="empty"):
            tts_service.synthesize("   \n  ", language="en")

    def test_unique_filenames(self):
        """Each synthesis should produce a unique filename."""
        r1 = tts_service.synthesize("Test one.", language="en")
        r2 = tts_service.synthesize("Test two.", language="en")

        assert r1["audio_path"] != r2["audio_path"]


class TestTextCleaning:
    """Tests for the internal text cleaning function."""

    def test_removes_brackets(self):
        """Should remove content inside square brackets."""
        cleaned = tts_service._clean_text("Hello [AI note] world")
        assert "[" not in cleaned
        assert "AI note" not in cleaned
        assert "Hello" in cleaned
        assert "world" in cleaned

    def test_removes_markdown_bold(self):
        """Should strip ** and * formatting."""
        cleaned = tts_service._clean_text("This is **bold** and *italic*")
        assert "**" not in cleaned
        assert "*" not in cleaned
        assert "bold" in cleaned

    def test_removes_markdown_headers(self):
        """Should strip # heading markers."""
        cleaned = tts_service._clean_text("## My Heading\nSome text")
        assert "##" not in cleaned
        assert "My Heading" in cleaned


# ==========================================
# Full Pipeline Integration Test
# ==========================================

class TestFullPipeline:
    """
    End-to-end test: Audio → STT → LLM → TTS → Audio out + DB save.
    This is the FINAL deliverable test for Week 4.
    """

    @pytest.fixture(scope="class")
    def test_audio_bytes(self):
        """Generate test audio."""
        from gtts import gTTS
        import io

        buffer = io.BytesIO()
        tts = gTTS("Explain what is artificial intelligence.", lang="en")
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()

    def test_complete_pipeline(self, test_audio_bytes):
        """
        The complete circle:
        Audio → STT → LLM (fallback) → TTS → Audio file + DB record.
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

        # Stage 2: Real transcript (not stub)
        assert len(data["transcript"]) > 0
        assert "[STT not connected yet]" not in data["transcript"]

        # Stage 4: Real reply (not stub)
        assert len(data["reply_text"]) > 0
        assert "[LLM not connected yet]" not in data["reply_text"]

        # Stage 5: Real audio file (not stub path)
        assert data["audio_url"].startswith("/outputs/response_")
        assert data["audio_url"] != "/outputs/stub_response.mp3"

        # Timing
        assert data["processing_time_ms"] > 0

    def test_conversation_saved_to_db(self, test_audio_bytes):
        """After processing, the conversation should appear in history."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        # Process an audio file
        client.post(
            "/api/process",
            files={"audio": ("test.mp3", test_audio_bytes, "audio/mpeg")},
            data={"target_language": "en", "persona_id": "1"},
        )

        # Check conversation history
        response = client.get("/api/personas/1/history")
        assert response.status_code == 200

        history = response.json()
        assert len(history) > 0

        latest = history[0]  # Most recent first
        assert "transcript" in latest
        assert "reply_text" in latest
        assert "reply_audio_path" in latest

    def test_audio_file_actually_exists(self, test_audio_bytes):
        """The generated audio file should exist on disk."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/api/process",
            files={"audio": ("test.mp3", test_audio_bytes, "audio/mpeg")},
            data={"target_language": "en", "persona_id": "1"},
        )

        data = response.json()
        # audio_url is like "/outputs/response_20260902_abc123.mp3"
        # actual file is at "outputs/response_20260902_abc123.mp3"
        file_path = data["audio_url"].lstrip("/")
        assert os.path.exists(file_path), f"Audio file not found: {file_path}"
        assert os.path.getsize(file_path) > 0, "Audio file is empty"
