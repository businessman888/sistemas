import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from app.core.database import get_db_connection
from app.modules.orchestrator.models import (
    ProjectCreate, ProjectResponse,
    PhaseCreate, PhaseResponse,
    ConnectionCreate, ConnectionResponse,
    CanvasSyncPayload,
    SubtaskCreate, SubtaskResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    """Lista todos os aplicativos cadastrados."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    """Cadastra um novo aplicativo."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO projects (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """, (project.name, project.description, now, now))
            conn.commit()
            project_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            return dict(row)
        except Exception as e:
            logger.exception("Erro ao criar projeto no banco")
            raise HTTPException(
                status_code=400,
                detail=f"O nome do aplicativo deve ser único. Detalhes: {e}"
            )

@router.get("/{id}")
async def get_project(id: int) -> Dict[str, Any]:
    """Retorna os detalhes completos do projeto, incluindo fases e conexões."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Obter projeto
        cursor.execute("SELECT * FROM projects WHERE id = ?", (id,))
        project_row = cursor.fetchone()
        if not project_row:
            raise HTTPException(status_code=404, detail="Aplicativo não encontrado.")
        
        # 2. Obter fases e suas subtarefas
        cursor.execute("SELECT * FROM project_phases WHERE project_id = ? ORDER BY id ASC", (id,))
        phases_rows = cursor.fetchall()
        
        phases = []
        for phase_row in phases_rows:
            p = dict(phase_row)
            cursor.execute("SELECT * FROM project_phase_subtasks WHERE phase_id = ? ORDER BY id ASC", (p["id"],))
            subtasks_rows = cursor.fetchall()
            p["subtasks"] = [dict(sub) for sub in subtasks_rows]
            phases.append(p)
        
        # 3. Obter conexões
        cursor.execute("SELECT * FROM project_connections WHERE project_id = ?", (id,))
        connections_rows = cursor.fetchall()
        
        return {
            "project": dict(project_row),
            "phases": phases,
            "connections": [dict(row) for row in connections_rows]
        }

@router.delete("/{id}")
async def delete_project(id: int):
    """Exclui um projeto e todos os seus dados associados."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Aplicativo não encontrado.")
        
        cursor.execute("DELETE FROM projects WHERE id = ?", (id,))
        conn.commit()
        
    return {"message": "Aplicativo removido com sucesso."}

@router.post("/{id}/phases", response_model=PhaseResponse)
async def create_phase(id: int, phase: PhaseCreate):
    """Adiciona uma nova fase ao aplicativo."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o projeto existe
        cursor.execute("SELECT id FROM projects WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Aplicativo não encontrado.")
        
        cursor.execute("""
        INSERT INTO project_phases (project_id, title, description, status, pos_x, pos_y)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (id, phase.title, phase.description, phase.status, phase.pos_x, phase.pos_y))
        
        phase_id = cursor.lastrowid
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
        cursor.execute("SELECT * FROM project_phases WHERE id = ?", (phase_id,))
        row = cursor.fetchone()
        return dict(row)

@router.put("/{id}/phases/{phase_id}", response_model=PhaseResponse)
async def update_phase(id: int, phase_id: int, phase: PhaseCreate):
    """Atualiza as informações e estado de uma fase."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a fase pertence ao projeto
        cursor.execute("SELECT id FROM project_phases WHERE id = ? AND project_id = ?", (phase_id, id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Fase não encontrada neste aplicativo.")
        
        cursor.execute("""
        UPDATE project_phases
        SET title = ?, description = ?, status = ?, pos_x = ?, pos_y = ?
        WHERE id = ?
        """, (phase.title, phase.description, phase.status, phase.pos_x, phase.pos_y, phase_id))
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
        cursor.execute("SELECT * FROM project_phases WHERE id = ?", (phase_id,))
        row = cursor.fetchone()
        p = dict(row)
        cursor.execute("SELECT * FROM project_phase_subtasks WHERE phase_id = ? ORDER BY id ASC", (phase_id,))
        subtasks_rows = cursor.fetchall()
        p["subtasks"] = [dict(sub) for sub in subtasks_rows]
        return p

@router.delete("/{id}/phases/{phase_id}")
async def delete_phase(id: int, phase_id: int):
    """Exclui uma fase específica do aplicativo."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a fase pertence ao projeto
        cursor.execute("SELECT id FROM project_phases WHERE id = ? AND project_id = ?", (phase_id, id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Fase não encontrada neste aplicativo.")
        
        cursor.execute("DELETE FROM project_phases WHERE id = ?", (phase_id,))
        
        # Conexões associadas serão removidas por cascata, mas por precaução executamos
        cursor.execute("DELETE FROM project_connections WHERE from_phase_id = ? OR to_phase_id = ?", (phase_id, phase_id))
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
    return {"message": "Fase removida com sucesso."}

@router.post("/{id}/canvas/sync")
async def sync_canvas(id: int, payload: CanvasSyncPayload):
    """Sincroniza em lote as posições dos nós e as conexões do Canvas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o projeto existe
        cursor.execute("SELECT id FROM projects WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Aplicativo não encontrado.")
        
        # 1. Atualizar posições dos nós
        for pos in payload.positions:
            cursor.execute("""
            UPDATE project_phases
            SET pos_x = ?, pos_y = ?
            WHERE id = ? AND project_id = ?
            """, (pos.pos_x, pos.pos_y, pos.id, id))
            
        # 2. Atualizar conexões (Delete-and-Insert simplificado e robusto)
        cursor.execute("DELETE FROM project_connections WHERE project_id = ?", (id,))
        
        for conn_data in payload.connections:
            # Validar se ambas as fases existem e pertencem a este projeto
            cursor.execute("""
            SELECT count(*) FROM project_phases 
            WHERE id IN (?, ?) AND project_id = ?
            """, (conn_data.from_phase_id, conn_data.to_phase_id, id))
            
            if cursor.fetchone()[0] == 2:
                try:
                    cursor.execute("""
                    INSERT INTO project_connections (project_id, from_phase_id, to_phase_id)
                    VALUES (?, ?, ?)
                    """, (id, conn_data.from_phase_id, conn_data.to_phase_id))
                except Exception:
                    # Ignorar conexões duplicadas acidentais
                    pass
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
    return {"status": "success"}

@router.post("/{id}/phases/{phase_id}/subtasks", response_model=SubtaskResponse)
async def create_subtask(id: int, phase_id: int, subtask: SubtaskCreate):
    """Adiciona uma nova subtarefa a uma fase específica."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a fase pertence ao projeto
        cursor.execute("SELECT id FROM project_phases WHERE id = ? AND project_id = ?", (phase_id, id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Fase não encontrada neste aplicativo.")
            
        cursor.execute("""
        INSERT INTO project_phase_subtasks (phase_id, title, status)
        VALUES (?, ?, ?)
        """, (phase_id, subtask.title, subtask.status))
        
        subtask_id = cursor.lastrowid
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
        cursor.execute("SELECT * FROM project_phase_subtasks WHERE id = ?", (subtask_id,))
        row = cursor.fetchone()
        return dict(row)

@router.put("/{id}/phases/{phase_id}/subtasks/{subtask_id}", response_model=SubtaskResponse)
async def update_subtask(id: int, phase_id: int, subtask_id: int, subtask: SubtaskCreate):
    """Atualiza o status ou título de uma subtarefa."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a subtarefa pertence à fase correta e se a fase pertence ao projeto
        cursor.execute("""
        SELECT s.id FROM project_phase_subtasks s
        JOIN project_phases p ON s.phase_id = p.id
        WHERE s.id = ? AND s.phase_id = ? AND p.project_id = ?
        """, (subtask_id, phase_id, id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Subtarefa não encontrada nesta fase/aplicativo.")
            
        cursor.execute("""
        UPDATE project_phase_subtasks
        SET title = ?, status = ?
        WHERE id = ?
        """, (subtask.title, subtask.status, subtask_id))
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
        cursor.execute("SELECT * FROM project_phase_subtasks WHERE id = ?", (subtask_id,))
        row = cursor.fetchone()
        return dict(row)

@router.delete("/{id}/phases/{phase_id}/subtasks/{subtask_id}")
async def delete_subtask(id: int, phase_id: int, subtask_id: int):
    """Exclui uma subtarefa."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a subtarefa pertence à fase correta
        cursor.execute("""
        SELECT s.id FROM project_phase_subtasks s
        JOIN project_phases p ON s.phase_id = p.id
        WHERE s.id = ? AND s.phase_id = ? AND p.project_id = ?
        """, (subtask_id, phase_id, id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Subtarefa não encontrada nesta fase/aplicativo.")
            
        cursor.execute("DELETE FROM project_phase_subtasks WHERE id = ?", (subtask_id,))
        
        # Atualiza a data de modificação do projeto
        now = datetime.now().isoformat()
        cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id))
        
        conn.commit()
        
    return {"message": "Subtarefa removida com sucesso."}
