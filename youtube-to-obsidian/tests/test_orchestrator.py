"""Testes para o Orquestrador de Projetos (fases, conexões e canvas)."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

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

    with patch("app.modules.orchestrator.routes.get_db_connection", side_effect=get_conn):
        with TestClient(app) as c:
            yield c


def test_create_and_list_projects(client):
    """Testa a criação e listagem de aplicativos/projetos."""
    # 1. Cria projeto
    response = client.post(
        "/api/projects",
        json={"name": "Oyto Test App", "description": "Aplicativo de teste do Orquestrador"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Oyto Test App"
    assert data["description"] == "Aplicativo de teste do Orquestrador"
    assert "id" in data
    project_id = data["id"]

    # 2. Lista projetos
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1
    assert any(p["id"] == project_id for p in projects)


def test_project_phases_lifecycle(client):
    """Testa a criação, atualização e remoção de fases individuais."""
    # 1. Cria projeto
    response = client.post("/api/projects", json={"name": "Lifecycle App"})
    project_id = response.json()["id"]

    # 2. Cria fase
    response = client.post(
        f"/api/projects/{project_id}/phases",
        json={
            "title": "Fase Inicial",
            "description": "Planejamento inicial",
            "status": "pending",
            "pos_x": 100.0,
            "pos_y": 100.0
        }
    )
    assert response.status_code == 200
    phase_data = response.json()
    assert phase_data["title"] == "Fase Inicial"
    phase_id = phase_data["id"]

    # 3. Atualiza fase (muda status para completed e move de lugar)
    response = client.put(
        f"/api/projects/{project_id}/phases/{phase_id}",
        json={
            "title": "Fase Inicial (Pronta)",
            "description": "Planejamento concluído",
            "status": "completed",
            "pos_x": 150.0,
            "pos_y": 200.0
        }
    )
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["status"] == "completed"
    assert updated_data["pos_x"] == 150.0

    # 4. Remove a fase
    response = client.delete(f"/api/projects/{project_id}/phases/{phase_id}")
    assert response.status_code == 200

    # 5. Garante que ela sumiu dos detalhes do projeto
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert len(response.json()["phases"]) == 0


def test_canvas_sync_and_get_details(client):
    """Testa a sincronização em lote do Canvas (nós e conexões)."""
    # 1. Cria projeto
    response = client.post("/api/projects", json={"name": "Canvas Sync App"})
    project_id = response.json()["id"]

    # 2. Cria duas fases
    p1_res = client.post(f"/api/projects/{project_id}/phases", json={"title": "UI Mockup", "status": "pending"})
    p2_res = client.post(f"/api/projects/{project_id}/phases", json={"title": "Database Setup", "status": "pending"})
    
    phase1_id = p1_res.json()["id"]
    phase2_id = p2_res.json()["id"]

    # 3. Sincroniza o canvas movendo os nós e criando uma conexão
    response = client.post(
        f"/api/projects/{project_id}/canvas/sync",
        json={
            "positions": [
                {"id": phase1_id, "pos_x": 120.0, "pos_y": 180.0},
                {"id": phase2_id, "pos_x": 350.0, "pos_y": 180.0}
            ],
            "connections": [
                {"from_phase_id": phase1_id, "to_phase_id": phase2_id}
            ]
        }
    )
    assert response.status_code == 200

    # 4. Puxa os dados completos do projeto para verificação
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    details = response.json()

    # Verifica se as posições dos nós foram atualizadas no banco
    phases = details["phases"]
    assert len(phases) == 2
    node1 = next(p for p in phases if p["id"] == phase1_id)
    node2 = next(p for p in phases if p["id"] == phase2_id)
    assert node1["pos_x"] == 120.0
    assert node2["pos_x"] == 350.0

    # Verifica se a conexão foi registrada no banco de dados
    connections = details["connections"]
    assert len(connections) == 1
    assert connections[0]["from_phase_id"] == phase1_id
    assert connections[0]["to_phase_id"] == phase2_id


def test_phase_subtasks_lifecycle(client):
    """Testa o ciclo de vida completo de subtarefas de uma fase."""
    # 1. Cria projeto
    response = client.post("/api/projects", json={"name": "Subtask Lifecycle App"})
    assert response.status_code == 200
    project_id = response.json()["id"]

    # 2. Cria fase
    response = client.post(
        f"/api/projects/{project_id}/phases",
        json={"title": "Fase de Teste de Subtarefa"}
    )
    assert response.status_code == 200
    phase_id = response.json()["id"]

    # 3. Adiciona subtarefa
    response = client.post(
        f"/api/projects/{project_id}/phases/{phase_id}/subtasks",
        json={"title": "Subtarefa Inicial", "status": "pending"}
    )
    assert response.status_code == 200
    subtask_data = response.json()
    assert subtask_data["title"] == "Subtarefa Inicial"
    assert subtask_data["status"] == "pending"
    subtask_id = subtask_data["id"]

    # 4. Obtém detalhes do projeto para verificar se a subtarefa está associada
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    details = response.json()
    phases = details["phases"]
    assert len(phases) == 1
    assert len(phases[0]["subtasks"]) == 1
    assert phases[0]["subtasks"][0]["id"] == subtask_id
    assert phases[0]["subtasks"][0]["title"] == "Subtarefa Inicial"

    # 5. Atualiza a subtarefa
    response = client.put(
        f"/api/projects/{project_id}/phases/{phase_id}/subtasks/{subtask_id}",
        json={"title": "Subtarefa Concluída", "status": "completed"}
    )
    assert response.status_code == 200
    updated_subtask = response.json()
    assert updated_subtask["title"] == "Subtarefa Concluída"
    assert updated_subtask["status"] == "completed"

    # 6. Verifica atualização via detalhes do projeto
    response = client.get(f"/api/projects/{project_id}")
    details = response.json()
    assert details["phases"][0]["subtasks"][0]["status"] == "completed"

    # 7. Exclui a subtarefa
    response = client.delete(f"/api/projects/{project_id}/phases/{phase_id}/subtasks/{subtask_id}")
    assert response.status_code == 200

    # 8. Garante que ela sumiu dos detalhes do projeto
    response = client.get(f"/api/projects/{project_id}")
    assert len(response.json()["phases"][0]["subtasks"]) == 0

