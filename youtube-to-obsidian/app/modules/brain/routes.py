import logging
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db_connection
from app.modules.brain.models import (
    BrainSessionCreate, BrainSessionResponse,
    BrainMessageCreate, BrainMessageResponse,
    SynthesisEstimateResponse, SourceDetail
)
from app.modules.brain.brain_service import (
    estimate_synthesis_cost, synthesize_vault_knowledge,
    generate_chat_stream, synthesis_lock
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brain", tags=["brain"])

@router.get("/synthesize/estimate", response_model=SynthesisEstimateResponse)
async def get_synthesis_estimate():
    """Retorna estimativa de quantidade de notas, tokens e custo para a síntese total."""
    try:
        data = estimate_synthesis_cost()
        return data
    except Exception as e:
        logger.exception("Erro ao estimar custo da síntese")
        raise HTTPException(status_code=500, detail=f"Erro ao calcular estimativa: {e}")

@router.get("/synthesize")
async def get_vault_synthesis():
    """Retorna a síntese do segundo cérebro existente no vault."""
    import frontmatter
    from pathlib import Path
    from app.core.config import settings
    synthesis_path = Path(settings.obsidian_vault_path) / "_OYTO" / "Sintese do Segundo Cerebro.md"
    if not synthesis_path.exists():
        raise HTTPException(status_code=404, detail="Nenhuma síntese encontrada. Por favor, gere uma nova síntese.")
    try:
        post = frontmatter.load(synthesis_path)
        return {
            "generated_at": post.metadata.get("generated_at", ""),
            "vault_size": post.metadata.get("vault_size", 0),
            "synthesis": post.content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler a nota de síntese: {e}")

@router.post("/synthesize")
async def trigger_vault_synthesis():
    """Dispara a síntese global de todo o conhecimento acumulado no vault."""
    if synthesis_lock.locked():
        raise HTTPException(status_code=429, detail="Uma síntese já está em andamento. Por favor, aguarde.")
    try:
        content = await synthesize_vault_knowledge()
        return {"status": "success", "synthesis": content}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=429, detail=str(re))
    except Exception as e:
        logger.exception("Erro durante a síntese de conhecimento")
        raise HTTPException(status_code=500, detail=f"Erro interno ao gerar síntese: {e}")

@router.get("/chat/sessions", response_model=List[BrainSessionResponse])
async def list_chat_sessions():
    """Lista todas as sessões de chat do Segundo Cérebro, ordenadas por atualização recente."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM brain_chat_sessions ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("/chat/sessions", response_model=BrainSessionResponse)
async def create_chat_session(session: BrainSessionCreate):
    """Cria uma nova sessão de chat (opcionalmente vinculando a uma persona)."""
    now = datetime.now().isoformat()
    title = session.title or "Nova Conversa"
    is_clone_only_val = 1 if session.is_clone_only else 0
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO brain_chat_sessions (title, persona_id, is_clone_only, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """, (title, session.persona_id, is_clone_only_val, now, now))
            conn.commit()
            
            session_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM brain_chat_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            return dict(row)
        except Exception as e:
            logger.exception("Erro ao criar sessão de chat no banco")
            raise HTTPException(status_code=500, detail=f"Erro ao salvar sessão: {e}")

@router.get("/chat/sessions/{id}/messages", response_model=List[BrainMessageResponse])
async def get_chat_session_messages(id: int):
    """Retorna o histórico completo de mensagens de uma sessão de chat."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Verifica se sessão existe
        cursor.execute("SELECT id FROM brain_chat_sessions WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Sessão de chat não encontrada.")
            
        cursor.execute("SELECT * FROM brain_chat_messages WHERE session_id = ? ORDER BY id ASC", (id,))
        rows = cursor.fetchall()
        
        messages = []
        for row in rows:
            row_dict = dict(row)
            # Converte sources_json de volta para lista de SourceDetail
            sources = []
            if row_dict.get("sources_json"):
                try:
                    sources_data = json.loads(row_dict["sources_json"])
                    sources = [SourceDetail(**s) for s in sources_data]
                except Exception:
                    pass
            
            messages.append(BrainMessageResponse(
                id=row_dict["id"],
                session_id=row_dict["session_id"],
                role=row_dict["role"],
                content=row_dict["content"],
                sources=sources if sources else None,
                tokens_input=row_dict.get("tokens_input", 0) or 0,
                tokens_output=row_dict.get("tokens_output", 0) or 0,
                cost_usd=row_dict.get("cost_usd", 0.0) or 0.0,
                created_at=row_dict["created_at"]
            ))
            
        return messages

@router.post("/chat/sessions/{id}/messages")
async def send_chat_message(id: int, message: BrainMessageCreate):
    """
    Envia uma nova pergunta na sessão de chat e recebe a resposta do Llama 4
    por streaming Server-Sent Events (SSE).
    """
    # Carrega a sessão para validar e descobrir se tem persona vinculada
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT persona_id, is_clone_only FROM brain_chat_sessions WHERE id = ?", (id,))
        session_row = cursor.fetchone()
        
    if not session_row:
        raise HTTPException(status_code=404, detail="Sessão de chat não encontrada.")
        
    persona_id = session_row["persona_id"]
    is_clone_only = True if session_row["is_clone_only"] == 1 else False
    
    # Retorna o streaming SSE usando EventSourceResponse
    async def sse_event_generator():
        async for sse_chunk in generate_chat_stream(
            session_id=id,
            user_message=message.content,
            persona_id=persona_id,
            is_clone_only=is_clone_only
        ):
            yield sse_chunk
            
    return EventSourceResponse(sse_event_generator())

@router.delete("/chat/sessions/{id}")
async def delete_chat_session(id: int):
    """Exclui a sessão de chat e todas as suas mensagens associadas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM brain_chat_sessions WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Sessão de chat não encontrada.")
            
        cursor.execute("DELETE FROM brain_chat_messages WHERE session_id = ?", (id,))
        cursor.execute("DELETE FROM brain_chat_sessions WHERE id = ?", (id,))
        conn.commit()
    return {"message": "Sessão de chat excluída com sucesso."}
