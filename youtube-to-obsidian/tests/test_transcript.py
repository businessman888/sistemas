"""Testes para o serviço de transcrição."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.video import TranscriptResult
from app.modules.youtube.transcript import fetch_transcript


class TestFetchTranscript:
    """Testes de busca de transcrição com mocks."""

    @patch("app.modules.youtube.transcript._api")
    def test_preferred_language_found(self, mock_api):
        """Retorna transcrição no idioma preferido quando disponível."""
        mock_transcript_list = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        mock_transcript = MagicMock()
        mock_entry_1 = MagicMock()
        mock_entry_1.text = "Olá mundo"
        mock_entry_1.start = 0.0
        mock_entry_1.duration = 5.0

        mock_entry_2 = MagicMock()
        mock_entry_2.text = "Como vai?"
        mock_entry_2.start = 5.0
        mock_entry_2.duration = 3.0

        mock_transcript.fetch.return_value = [mock_entry_1, mock_entry_2]
        mock_transcript_list.find_transcript.return_value = mock_transcript

        # Mock __iter__ para _build_language_priority
        mock_lang = MagicMock()
        mock_lang.language_code = "pt"
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_lang]))

        result = fetch_transcript("test123", preferred_language="pt")

        assert isinstance(result, TranscriptResult)
        assert result.language == "pt"
        assert len(result.segments) == 2
        assert result.segments[0].text == "Olá mundo"

    @patch("app.modules.youtube.transcript._api")
    def test_no_transcripts_raises(self, mock_api):
        """Levanta ValueError quando não há legendas."""
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api.list.side_effect = TranscriptsDisabled("test123")

        with pytest.raises(ValueError, match="legendas"):
            fetch_transcript("test123")

    @patch("app.modules.youtube.transcript._api")
    def test_video_unavailable_raises(self, mock_api):
        """Levanta LookupError quando vídeo não existe."""
        from youtube_transcript_api._errors import VideoUnavailable

        mock_api.list.side_effect = VideoUnavailable("test123")

        with pytest.raises(LookupError):
            fetch_transcript("test123")

    @patch("app.modules.youtube.transcript._api")
    def test_ip_blocked_on_list_raises(self, mock_api):
        """Levanta ConnectionError quando o YouTube bloqueia o IP na listagem."""
        from youtube_transcript_api._errors import IpBlocked

        mock_api.list.side_effect = IpBlocked("test123")

        with pytest.raises(ConnectionError, match="IP bloqueado"):
            fetch_transcript("test123")

    @patch("app.modules.youtube.transcript._api")
    def test_ip_blocked_on_fetch_raises(self, mock_api):
        """Levanta ConnectionError quando o YouTube bloqueia o IP no fetch da transcrição."""
        from youtube_transcript_api._errors import IpBlocked

        mock_transcript_list = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        mock_transcript = MagicMock()
        mock_transcript.fetch.side_effect = IpBlocked("test123")
        mock_transcript_list.find_transcript.return_value = mock_transcript

        # Mock __iter__ para _build_language_priority
        mock_lang = MagicMock()
        mock_lang.language_code = "pt"
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_lang]))

        with pytest.raises(ConnectionError, match="IP bloqueado"):
            fetch_transcript("test123", preferred_language="pt")
