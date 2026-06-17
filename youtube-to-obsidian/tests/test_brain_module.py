import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

# Adiciona o diretório do projeto ao sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import init_db
from app.main import app


@pytest.fixture
def test_db():
    """Cria um banco de dados SQLite temporário e inicializa as tabelas."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Patch do database_path antes de rodar o init_db
    with patch("app.core.database.settings.database_path", temp_db_path):
        init_db()
        yield temp_db_path

    # Deleta o arquivo após o teste
    try:
        os.unlink(temp_db_path)
    except OSError:
        pass


@pytest.fixture
def client(test_db):
    """Retorna um TestClient com a conexão de banco de dados mockada para usar o banco temporário."""
    def get_conn():
        import sqlite3
        conn = sqlite3.connect(test_db)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    with patch("app.modules.brain.routes.get_db_connection", side_effect=get_conn), \
         patch("app.modules.brain.brain_service.get_db_connection", side_effect=get_conn):
        with TestClient(app) as c:
            yield c


def test_brain_sessions_lifecycle(client):
    """Testa a criação, listagem e busca de histórico de sessões de chat."""
    # 1. Cria sessão de chat
    response = client.post(
        "/api/brain/chat/sessions",
        json={"title": "Test Chat Session", "persona_id": None, "is_clone_only": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Chat Session"
    assert "id" in data
    session_id = data["id"]

    # 2. Lista sessões
    response = client.get("/api/brain/chat/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) >= 1
    assert any(s["id"] == session_id for s in sessions)

    # 3. Busca mensagens de uma sessão vazia
    response = client.get(f"/api/brain/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 0


@patch("app.core.config.settings")
def test_synthesis_estimate(mock_settings, client):
    """Testa a rota de estimativa de custo para a síntese."""
    mock_settings.obsidian_vault_path = "/mock_vault"
    
    with patch("app.modules.brain.brain_service.get_vault_notes") as mock_notes:
        mock_notes.return_value = [
            {"title": "Note 1", "channel": "C1", "tags": [], "content": "hello " * 100},
            {"title": "Note 2", "channel": "C2", "tags": [], "content": "world " * 200}
        ]
        response = client.get("/api/brain/synthesize/estimate")
        assert response.status_code == 200
        data = response.json()
        assert data["total_notes"] == 2
        assert data["estimated_tokens"] > 0
        assert "estimated_cost_usd" in data


@patch("app.core.config.settings")
def test_get_synthesis_not_found(mock_settings, client):
    """Testa a obtenção de síntese inexistente."""
    mock_settings.obsidian_vault_path = "/mock_vault"
    
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False
        response = client.get("/api/brain/synthesize")
        assert response.status_code == 404


@patch("app.core.config.settings")
def test_get_synthesis_success(mock_settings, client):
    """Testa a obtenção de síntese existente."""
    mock_settings.obsidian_vault_path = "/mock_vault"
    
    # Mock do frontmatter.load
    mock_post = MagicMock()
    mock_post.content = "Esta é uma síntese estruturada de teste."
    mock_post.metadata = {"generated_at": "2026-06-03T19:00:00", "vault_size": 5}
    
    with patch("pathlib.Path.exists") as mock_exists, \
         patch("frontmatter.load") as mock_load:
        mock_exists.return_value = True
        mock_load.return_value = mock_post
        
        response = client.get("/api/brain/synthesize")
        assert response.status_code == 200
        data = response.json()
        assert data["synthesis"] == "Esta é uma síntese estruturada de teste."
        assert data["generated_at"] == "2026-06-03T19:00:00"
        assert data["vault_size"] == 5




@patch("app.modules.brain.brain_service.astream_llm")
@patch("app.modules.brain.brain_service.get_vault_notes")
def test_chat_message_streaming(mock_vault_notes, mock_stream, client):
    """Testa o streaming SSE de envio de mensagens do chat."""
    # 1. Cria uma sessão de chat
    session_res = client.post(
        "/api/brain/chat/sessions",
        json={"title": "Streaming Session", "persona_id": None, "is_clone_only": False}
    )
    session_id = session_res.json()["id"]

    # 2. Mock do vault notes
    mock_vault_notes.return_value = [
        {"title": "Note A", "channel": "Channel A", "tags": [], "content": "Algum conteúdo sobre marketing digital", "relative_path": "Note_A.md", "source": "youtube"}
    ]

    # 3. Mock do stream do Claude (gerador assíncrono)
    async def mock_generator(*args, **kwargs):
        for token in ["Olá", " ", "Mundo", "!"]:
            yield token
    mock_stream.side_effect = mock_generator

    # 4. Envia mensagem do chat
    response = client.post(
        f"/api/brain/chat/sessions/{session_id}/messages",
        json={"content": "Quais são as melhores ideias de negócios?"}
    )
    assert response.status_code == 200
    
    # Valida o formato SSE na resposta
    sse_text = response.text
    assert "event: search" in sse_text
    assert "event: token" in sse_text
    assert "event: done" in sse_text
    assert "Ol\\u00e1" in sse_text
    assert "Mundo" in sse_text

