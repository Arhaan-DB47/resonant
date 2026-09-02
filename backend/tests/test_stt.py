"""
test_stt.py -- Tests for the STT Service and Audio Utils

Run with:
    pytest backend/tests/test_stt.py -v
"""

import os
import sys
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.utils.audio_utils import save_upload, convert_to_wav, cleanup_temp_files, SUPPORTED_FORMATS


# ==========================================
# Audio Utils Tests
# ==========================================

class TestSaveUpload:
    """Tests for the save_upload function."""

    def test_save_valid_wav(self):
        """Should save a valid WAV file and return the path."""
        fake_audio = b"RIFF" + b"\x00" * 100  # Minimal WAV-like bytes
        path = save_upload(fake_audio, "test.wav")
        assert os.path.exists(path)
        assert path.endswith(".wav")
        cleanup_temp_files(path)

    def test_save_valid_mp3(self):
        """Should save a valid MP3 file."""
        fake_audio = b"\xff\xfb" + b"\x00" * 100
        path = save_upload(fake_audio, "recording.mp3")
        assert os.path.exists(path)
        assert path.endswith(".mp3")
        cleanup_temp_files(path)

    def test_save_valid_webm(self):
        """Should save a valid WebM file."""
        fake_audio = b"\x1a\x45" + b"\x00" * 100
        path = save_upload(fake_audio, "recording.webm")
        assert os.path.exists(path)
        assert path.endswith(".webm")
        cleanup_temp_files(path)

    def test_reject_empty_file(self):
        """Should reject a zero-byte file."""
        with pytest.raises(ValueError, match="empty"):
            save_upload(b"", "test.wav")

    def test_reject_unsupported_format(self):
        """Should reject formats not in the supported list."""
        with pytest.raises(ValueError, match="Unsupported"):
            save_upload(b"some data", "test.txt")

    def test_reject_too_large(self):
        """Should reject files over 10 MB."""
        huge_file = b"\x00" * (11 * 1024 * 1024)  # 11 MB
        with pytest.raises(ValueError, match="too large"):
            save_upload(huge_file, "huge.wav")


class TestCleanup:
    """Tests for the cleanup function."""

    def test_cleanup_removes_temp_files(self):
        """Should delete files with 'resonant_' in the name."""
        # Create a temp file matching the naming pattern
        path = os.path.join(tempfile.gettempdir(), "resonant_test123.wav")
        with open(path, "w") as f:
            f.write("test")
        assert os.path.exists(path)

        cleanup_temp_files(path)
        assert not os.path.exists(path)

    def test_cleanup_ignores_none(self):
        """Should not crash on None paths."""
        cleanup_temp_files(None, "", None)  # Should not raise

    def test_cleanup_ignores_nonexistent(self):
        """Should not crash on paths that don't exist."""
        cleanup_temp_files("/fake/resonant_path.wav")  # Should not raise


# ==========================================
# STT Service Tests (requires model download)
# ==========================================

class TestSTTService:
    """
    Integration tests for the STT service.
    These require the Whisper model to be downloaded (~75 MB for tiny).
    They use gTTS to generate real test audio.
    """

    @pytest.fixture(scope="class")
    def english_audio(self):
        """Generate a test audio file using gTTS."""
        from gtts import gTTS
        path = os.path.join(tempfile.gettempdir(), "resonant_test_en.mp3")
        tts = gTTS("What is machine learning and how does it work?", lang="en")
        tts.save(path)
        yield path
        cleanup_temp_files(path)

    @pytest.fixture(scope="class")
    def hindi_audio(self):
        """Generate a Hindi test audio file using gTTS."""
        from gtts import gTTS
        path = os.path.join(tempfile.gettempdir(), "resonant_test_hi.mp3")
        tts = gTTS("मशीन लर्निंग क्या है?", lang="hi")
        tts.save(path)
        yield path
        cleanup_temp_files(path)

    def test_transcribe_english(self, english_audio):
        """Should transcribe English audio and detect the language."""
        from backend.services.stt_service import stt_service

        result = stt_service.transcribe(english_audio)

        assert result["transcript"], "Transcript should not be empty"
        assert result["language"] == "en", f"Expected 'en', got '{result['language']}'"
        assert result["confidence"] > 0.5, "Confidence should be > 50%"
        assert result["duration_ms"] > 0, "Duration should be positive"
        assert "machine learning" in result["transcript"].lower(), (
            f"Expected 'machine learning' in transcript, got: {result['transcript']}"
        )

    def test_transcribe_hindi(self, hindi_audio):
        """Should transcribe Hindi audio and detect the language."""
        from backend.services.stt_service import stt_service

        result = stt_service.transcribe(hindi_audio)

        assert result["transcript"], "Transcript should not be empty"
        assert result["language"] == "hi", f"Expected 'hi', got '{result['language']}'"
        assert result["confidence"] > 0.3, "Confidence should be > 30%"
        assert result["duration_ms"] > 0, "Duration should be positive"

    def test_transcribe_with_language_hint(self, english_audio):
        """Should accept a language hint and still transcribe correctly."""
        from backend.services.stt_service import stt_service

        result = stt_service.transcribe(english_audio, language="en")

        assert result["transcript"], "Transcript should not be empty"
        assert result["language"] == "en"

    def test_transcribe_nonexistent_file(self):
        """Should raise FileNotFoundError for missing files."""
        from backend.services.stt_service import stt_service

        with pytest.raises(FileNotFoundError):
            stt_service.transcribe("/nonexistent/audio.wav")

    def test_transcribe_empty_file(self):
        """Should raise ValueError for empty files."""
        from backend.services.stt_service import stt_service

        # Create an empty file
        path = os.path.join(tempfile.gettempdir(), "resonant_empty.wav")
        open(path, "w").close()

        with pytest.raises(ValueError, match="empty"):
            stt_service.transcribe(path)

        cleanup_temp_files(path)


# ==========================================
# API Integration Test
# ==========================================

class TestProcessEndpoint:
    """Test the POST /api/process endpoint with real audio."""

    @pytest.fixture(scope="class")
    def test_audio_bytes(self):
        """Generate test audio bytes."""
        from gtts import gTTS
        import io
        buffer = io.BytesIO()
        tts = gTTS("Hello, this is a test of the speech recognition system.", lang="en")
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()

    def test_process_endpoint(self, test_audio_bytes):
        """Should transcribe uploaded audio via the API."""
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

        # Transcript should contain real text (not the old stub)
        assert "[STT not connected yet]" not in data["transcript"], (
            "STT is still returning the stub response!"
        )
        assert len(data["transcript"]) > 0
        assert data["processing_time_ms"] > 0

    def test_process_rejects_bad_format(self):
        """Should return 400 for unsupported audio formats."""
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        response = client.post(
            "/api/process",
            files={"audio": ("test.txt", b"not audio", "text/plain")},
            data={"target_language": "en", "persona_id": "1"},
        )

        assert response.status_code == 400
