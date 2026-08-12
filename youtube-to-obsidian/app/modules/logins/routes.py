import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Form, Query

from app.core.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logins", tags=["logins"])


def row_to_dict(row):
    if not row:
        return None
    return dict(row)


@router.get("")
@router.get("/")
async def list_credentials():
    """List all credentials, ordered by service_name."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM credentials ORDER BY service_name ASC")
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows]


@router.post("")
@router.post("/")
async def create_credential(
    service_name: str = Form(...),
    login: str = Form(...),
    password: str = Form(""),
    notes: str = Form(""),
    category: str = Form("Geral")
):
    """Create a new credential."""
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO credentials (service_name, login, password, notes, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (service_name.strip(), login.strip(), password, notes, category, now, now)
            )
            conn.commit()
            item_id = cursor.lastrowid

            cursor.execute("SELECT * FROM credentials WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao cadastrar credencial")
            raise HTTPException(status_code=400, detail=f"Erro ao cadastrar credencial: {e}")


@router.put("/{credential_id}")
@router.put("/{credential_id}/")
async def update_credential(
    credential_id: int,
    service_name: str = Form(...),
    login: str = Form(...),
    password: str = Form(""),
    notes: str = Form(""),
    category: str = Form("Geral")
):
    """Update an existing credential."""
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Credencial não encontrada.")

        try:
            cursor.execute(
                """
                UPDATE credentials
                SET service_name = ?, login = ?, password = ?, notes = ?, category = ?, updated_at = ?
                WHERE id = ?
                """,
                (service_name.strip(), login.strip(), password, notes, category, now, credential_id)
            )
            conn.commit()

            cursor.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao atualizar credencial")
            raise HTTPException(status_code=400, detail=f"Erro ao atualizar credencial: {e}")


@router.delete("/{credential_id}")
async def delete_credential(credential_id: int):
    """Delete a credential."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Credencial não encontrada.")

        try:
            cursor.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
            conn.commit()
            return {"message": "Credencial removida com sucesso."}
        except Exception as e:
            logger.exception("Erro ao excluir credencial")
            raise HTTPException(status_code=400, detail=f"Erro ao excluir credencial: {e}")
