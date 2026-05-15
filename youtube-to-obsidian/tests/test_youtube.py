"""Testes para o serviço de YouTube: validação de URL e extração de metadados."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.youtube import extract_video_id, fetch_video_metadata, validate_youtube_url


class TestExtractVideoId:
    """Testes de extração de video_id de diferentes formatos de URL."""

    def test_standard_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_standard_url_with_extra_params(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_without_https(self):
        assert extract_video_id("youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_http_url(self):
        assert extract_video_id("http://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_url(self):
        assert extract_video_id("https://www.google.com") is None

    def test_empty_string(self):
        assert extract_video_id("") is None

    def test_random_text(self):
        assert extract_video_id("não é uma url") is None

    def test_youtube_homepage(self):
        assert extract_video_id("https://www.youtube.com") is None


class TestValidateYoutubeUrl:
    """Testes de validação de URL com error handling."""

    def test_valid_url_returns_id(self):
        assert validate_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="URL inválida"):
            validate_youtube_url("https://www.google.com")


class TestFetchVideoMetadata:
    """Testes de busca de metadados via yt-dlp (com mock)."""

    @patch("app.services.youtube.yt_dlp.YoutubeDL")
    def test_success(self, mock_ydl_class):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "channel_url": "https://www.youtube.com/@test",
            "upload_date": "20240101",
            "duration": 300,
            "description": "Test description",
            "thumbnail": "https://i.ytimg.com/vi/test123/maxresdefault.jpg",
        }

        result = fetch_video_metadata("test123")

        assert result.video_id == "test123"
        assert result.title == "Test Video"
        assert result.channel == "Test Channel"
        assert result.duration == 300

    @patch("app.services.youtube.yt_dlp.YoutubeDL")
    def test_video_not_found(self, mock_ydl_class):
        import yt_dlp

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("Video unavailable")

        with pytest.raises(LookupError):
            fetch_video_metadata("invalid123")
