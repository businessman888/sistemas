import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.core.database import get_db_connection
from app.modules.clone.models import (
    CloneCreate, CloneResponse,
    MessageCreate, MessageResponse
)
from app.modules.clone.clone_service import (
    run_cloning_pipeline, generate_chat_response
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clones", tags=["clones"])

@router.get("", response_model=List[CloneResponse])
async def list_clones():
    """Lista todos os clones mentais cadastrados."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clones ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("", response_model=CloneResponse)
async def create_clone(clone: CloneCreate, background_tasks: BackgroundTasks):
    """Cria um novo clone e inicia a transcrição/análise em background."""
    now = datetime.now().isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO clones (name, channel_url, max_videos, status, created_at, updated_at)
            VALUES (?, ?, ?, 'transcribing', ?, ?)
            """, (clone.name, clone.channel_url, clone.max_videos, now, now))
            conn.commit()
            
            clone_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM clones WHERE id = ?", (clone_id,))
            row = cursor.fetchone()
            
        except Exception as e:
            logger.exception("Erro ao criar clone no banco")
            raise HTTPException(
                status_code=400,
                detail=f"Nome do clone deve ser único. Detalhes: {e}"
            )
            
    # Dispara o pipeline de processamento em segundo plano
    background_tasks.add_task(run_cloning_pipeline, clone_id)
    
    return dict(row)

@router.get("/{id}", response_model=CloneResponse)
async def get_clone(id: int):
    """Retorna detalhes de um clone específico."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clones WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Clone mental não encontrado.")
        return dict(row)

@router.delete("/{id}")
async def delete_clone(id: int):
    """Exclui um clone e seu histórico de mensagens do banco."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Cascade delete não precisa ser manual se definirmos ON DELETE CASCADE, 
        # mas por garantia vamos remover mensagens e o clone
        cursor.execute("DELETE FROM clone_messages WHERE clone_id = ?", (id,))
        cursor.execute("DELETE FROM clones WHERE id = ?", (id,))
        conn.commit()
    return {"message": "Clone mental removido com sucesso."}

@router.post("/{id}/build_blueprint")
async def build_clone_blueprint(id: int):
    """Gera o Master Mental Model Blueprint do clone e salva no vault."""
    try:
        from app.modules.clone.clone_service import generate_clone_blueprint
        blueprint_markdown = await generate_clone_blueprint(id)
        return {"status": "success", "blueprint": blueprint_markdown}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Erro ao gerar blueprint para o clone")
        raise HTTPException(status_code=500, detail=f"Erro interno de processamento da IA: {e}")

@router.get("/{id}/messages", response_model=List[MessageResponse])
async def get_clone_messages(id: int):
    """Retorna o histórico de conversas com um clone."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clone_messages WHERE clone_id = ? ORDER BY id ASC", (id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("/{id}/messages")
async def send_message_to_clone(id: int, message: MessageCreate):
    """Envia uma mensagem para o clone e retorna a resposta gerada."""
    try:
        response_text = await generate_chat_response(id, message.content)
        return {"response": response_text}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Erro ao processar conversa com o clone")
        raise HTTPException(status_code=500, detail=f"Erro interno de processamento da IA: {e}")

@router.delete("/{id}/messages")
async def clear_clone_messages(id: int):
    """Limpa o histórico de chat de um clone."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clone_messages WHERE clone_id = ?", (id,))
        conn.commit()
    return {"message": "Histórico de conversa limpo."}
