import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# Adiciona o diretório do projeto ao sys.path
sys.path.append(str(Path("c:/systems/sistemas/youtube-to-obsidian")))

from app.modules.clone.clone_service import fetch_channel_videos, search_local_transcripts, generate_chat_response

class TestCloneService:
    @patch("app.modules.clone.clone_service.yt_dlp.YoutubeDL")
    def test_fetch_channel_videos_success(self, mock_ydl_class):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {"id": "video1"},
                {"id": "video2"},
                {"id": "video3"}
            ]
        }
        
        result = fetch_channel_videos("https://youtube.com/@test", limit=2)
        assert result == ["video1", "video2"]
        
    @patch("app.modules.clone.clone_service.yt_dlp.YoutubeDL")
    def test_fetch_channel_videos_empty(self, mock_ydl_class):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = None
        
        result = fetch_channel_videos("https://youtube.com/@test", limit=5)
        assert result == []

    @patch("app.modules.clone.clone_service.settings")
    @patch("app.modules.clone.clone_service.Path.exists")
    @patch("app.modules.clone.clone_service.Path.glob")
    def test_search_local_transcripts_empty(self, mock_glob, mock_exists, mock_settings):
        mock_settings.obsidian_vault_path = "C:/mock_vault"
        mock_exists.return_value = False
        
        result = search_local_transcripts("Test Clone", "business ideas")
        assert result == []

    @patch("app.modules.clone.clone_service.settings")
    @patch("app.modules.clone.clone_service.Path.exists")
    @patch("app.modules.clone.clone_service.Path.glob")
    def test_search_local_transcripts_with_files(self, mock_glob, mock_exists, mock_settings):
        mock_settings.obsidian_vault_path = "C:/mock_vault"
        mock_exists.return_value = True
        
        # Mock do conteúdo do arquivo 1
        content1 = (
            "# Video 1\n"
            "## 📜 Transcrição\n"
            "### [00:00]\n"
            "Eu sempre defendo que você deve precificar alto seus produtos de negócios digitais.\n"
            "### [00:30]\n"
            "A estratégia de vendas depende muito de gerar valor perceptível."
        )
        # Mock do conteúdo do arquivo 2
        content2 = (
            "# Video 2\n"
            "## 📜 Transcrição\n"
            "### [00:00]\n"
            "Receitas de bolo de cenoura com chocolate são fáceis de fazer em casa."
        )

        # Cria caminhos de arquivo mockados
        mock_file1 = MagicMock()
        mock_file1.read_text.return_value = content1
        
        mock_file2 = MagicMock()
        mock_file2.read_text.return_value = content2
        
        mock_glob.return_value = [mock_file1, mock_file2]
        
        # Teste 1: buscando algo que combina com o vídeo 1
        result = search_local_transcripts("Test Clone", "precificar produtos digitais")
        assert len(result) > 0
        assert "precificar alto" in result[0]
        
        # Teste 2: buscando algo que combina com o vídeo 2
        result_cake = search_local_transcripts("Test Clone", "bolo de cenoura")
        assert len(result_cake) > 0
        assert "bolo de cenoura" in result_cake[0]


