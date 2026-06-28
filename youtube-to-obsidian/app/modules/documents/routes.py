import logging
import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Helper function to get clean database rows as dicts
def row_to_dict(row):
    return dict(row) if row else None

@router.get("/categories")
async def list_categories():
    """Lista todas as categorias de documentos."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM document_categories ORDER BY name ASC")
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows]

@router.post("/categories")
async def create_category(name: str = Form(...), parent_id: Optional[int] = Form(None)):
    """Cria uma nova categoria ou subcategoria."""
    now = datetime.now().isoformat()
    # Limpa parent_id se vier como 0 ou None de string
    if parent_id == 0 or parent_id == -1:
        parent_id = None
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO document_categories (name, parent_id, created_at) VALUES (?, ?, ?)",
                (name.strip(), parent_id, now)
            )
            conn.commit()
            cat_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM document_categories WHERE id = ?", (cat_id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao criar categoria")
            raise HTTPException(status_code=400, detail=f"Erro ao criar categoria: {e}")

@router.put("/categories/{id}")
async def update_category(id: int, name: str = Form(...)):
    """Renomeia uma categoria."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM document_categories WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Categoria não encontrada.")
            
        try:
            cursor.execute("UPDATE document_categories SET name = ? WHERE id = ?", (name.strip(), id))
            conn.commit()
            
            cursor.execute("SELECT * FROM document_categories WHERE id = ?", (id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao atualizar categoria")
            raise HTTPException(status_code=400, detail=f"Erro ao atualizar categoria: {e}")

@router.delete("/categories/{id}")
async def delete_category(id: int):
    """Exclui uma categoria (e subcategorias via cascade)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM document_categories WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Categoria não encontrada.")
            
        try:
            # SQLite cascade excluirá subcategorias associadas se pragma foreign_keys estiver ON.
            # E mudará documentos vinculados para category_id = NULL.
            cursor.execute("DELETE FROM document_categories WHERE id = ?", (id,))
            conn.commit()
            return {"message": "Categoria removida com sucesso."}
        except Exception as e:
            logger.exception("Erro ao excluir categoria")
            raise HTTPException(status_code=400, detail=f"Erro ao excluir categoria: {e}")

@router.get("")
async def list_documents(category_id: Optional[int] = None, search: Optional[str] = None):
    """Lista todos os documentos com filtros opcionais."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM documents"
        params = []
        conditions = []
        
        if category_id is not None:
            if category_id == -1: # Representa "Avulsos" no frontend
                conditions.append("category_id IS NULL")
            else:
                conditions.append("category_id = ?")
                params.append(category_id)
                
        if search:
            conditions.append("original_name LIKE ?")
            params.append(f"%{search.strip()}%")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows]

@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    category_id: Optional[int] = Form(None)
):
    """Realiza o upload de um documento e salva localmente."""
    # Trata category_id inválidos
    if category_id == 0 or category_id == -1:
        category_id = None
        
    # Assegura que o diretório de destino existe
    storage_dir = Path(settings.documents_storage_path)
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.exception("Erro ao criar pasta de documentos")
        raise HTTPException(
            status_code=500,
            detail=f"Não foi possível criar o diretório de arquivos: {e}"
        )
        
    # Gera um nome de arquivo físico seguro e único para evitar colisões no Windows
    original_name = file.filename or "arquivo_sem_nome"
    suffix = Path(original_name).suffix
    unique_filename = f"{uuid.uuid4().hex}{suffix}"
    dest_path = storage_dir / unique_filename
    
    # Salva o arquivo no disco
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.exception("Erro ao salvar arquivo no disco")
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao gravar arquivo no disco: {e}"
        )
    finally:
        await file.close()
        
    # Obtém o tamanho do arquivo gravado
    file_size = dest_path.stat().st_size
    now = datetime.now().isoformat()
    
    # Registra no banco de dados
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO documents (filename, original_name, file_path, file_size, mime_type, category_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (unique_filename, original_name, str(dest_path.as_posix()), file_size, file.content_type, category_id, now)
            )
            conn.commit()
            doc_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            # Em caso de erro, tenta apagar o arquivo criado para não deixar lixo no disco
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            logger.exception("Erro ao registrar documento no banco")
            raise HTTPException(status_code=400, detail=f"Erro ao salvar registro do arquivo: {e}")

@router.put("/{id}")
async def update_document(
    id: int,
    original_name: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None)
):
    """Atualiza metadados do documento (renomear ou mover categoria)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento não encontrado.")
            
        doc_dict = row_to_dict(doc)
        
        # Limpa category_id do form
        # Se for -1 no form, representa desvincular (setar None)
        target_category = doc_dict["category_id"]
        if category_id is not None:
            target_category = None if (category_id == -1 or category_id == 0) else category_id
            
        target_name = original_name.strip() if original_name else doc_dict["original_name"]
        
        try:
            cursor.execute(
                "UPDATE documents SET original_name = ?, category_id = ? WHERE id = ?",
                (target_name, target_category, id)
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM documents WHERE id = ?", (id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao atualizar documento")
            raise HTTPException(status_code=400, detail=f"Erro ao atualizar documento: {e}")

@router.delete("/{id}")
async def delete_document(id: int):
    """Remove o documento do banco e apaga o arquivo do disco."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Documento não encontrado.")
            
        doc = row_to_dict(row)
        file_path = Path(doc["file_path"])
        
        try:
            # Remove o registro do banco
            cursor.execute("DELETE FROM documents WHERE id = ?", (id,))
            conn.commit()
            
            # Remove o arquivo físico
            if file_path.exists():
                file_path.unlink()
                
            return {"message": "Documento excluído com sucesso."}
        except Exception as e:
            logger.exception("Erro ao excluir documento")
            raise HTTPException(status_code=400, detail=f"Erro ao excluir documento: {e}")

@router.get("/{id}/file")
async def get_document_file(id: int):
    """Retorna o arquivo físico para visualização ou download."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Documento não encontrado.")
            
        doc = row_to_dict(row)
        file_path = Path(doc["file_path"])
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Arquivo físico não encontrado no servidor.")
            
        # Retorna o arquivo de forma a poder ser exibido no navegador
        return FileResponse(
            path=str(file_path.resolve()),
            media_type=doc["mime_type"],
            filename=doc["original_name"]
        )
