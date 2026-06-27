import os
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, AsyncIterator
import frontmatter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.core.config import settings
from app.core.database import get_db_connection
from app.core.anthropic_client import ainvoke_llm, astream_llm, usage_tracker
from app.core.similarity import _get_stopwords

logger = logging.getLogger(__name__)

# Lock global para limitar concorrência na síntese a 1 por vez
synthesis_lock = asyncio.Lock()

def get_clone_name_by_id(persona_id: int) -> Optional[str]:
    """Retorna o nome do clone pelo ID cadastrado no banco."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM clones WHERE id = ?", (persona_id,))
        row = cursor.fetchone()
        return row["name"] if row else None

def get_vault_notes(persona_id: Optional[int] = None, is_clone_only: bool = False) -> List[Dict[str, Any]]:
    """
    Varre o Obsidian Vault e extrai notas úteis baseadas nos filtros.
    Se is_clone_only for True, retorna apenas notas do clone específico.
    Caso contrário, retorna todas as notas com source: youtube.
    """
    vault_path = Path(settings.obsidian_vault_path)
    notes = []
    
    if not vault_path.exists():
        logger.warning("Caminho do Obsidian Vault não existe: %s", vault_path)
        return notes

    clone_name = None
    if persona_id:
        clone_name = get_clone_name_by_id(persona_id)

    for md_file in vault_path.rglob("*.md"):
        # Ignora pastas de sistema do Obsidian e do Oyto OS (_OYTO)
        relative_path = md_file.relative_to(vault_path)
        parts = relative_path.parts
        if any(p.startswith(".") or p.startswith("_OYTO") or p.startswith("_") for p in parts):
            continue

        try:
            # Carrega a nota e seu frontmatter usando python-frontmatter
            post = frontmatter.load(md_file)
            meta = post.metadata
            
            # Filtro para Mente Clone
            if is_clone_only:
                if not clone_name:
                    continue
                # Verifica se a nota está na pasta de vídeos do clone ou se o metadado bate
                is_in_clone_folder = "Brains" in parts and clone_name in parts
                matches_meta = meta.get("clone_name") == clone_name or slugify_name(meta.get("clone_name", "")) == slugify_name(clone_name)
                
                if not (is_in_clone_folder or matches_meta):
                    continue
            else:
                # Segundo Cérebro comum: busca apenas source: youtube (ou mind-clone)
                source = meta.get("source")
                if source not in ["youtube", "mind-clone"]:
                    continue

            # Extrai o conteúdo relevante (título, descrição original e transcrição)
            content = post.content or ""
            notes.append({
                "title": meta.get("title") or md_file.stem,
                "channel": meta.get("channel") or "",
                "tags": meta.get("tags") or [],
                "content": content,
                "file_path": str(md_file),
                "relative_path": str(relative_path).replace("\\", "/"),
                "source": meta.get("source", "")
            })
        except Exception as e:
            logger.warning("Erro ao ler frontmatter da nota %s: %s", md_file, e)
            continue
            
    return notes

def slugify_name(name: str) -> str:
    """Normaliza o nome para comparação."""
    import re
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower() if name else ""

def estimate_synthesis_cost() -> Dict[str, Any]:
    """Retorna estatísticas estimadas de custo para a síntese."""
    notes = get_vault_notes(persona_id=None, is_clone_only=False)
    total_notes = len(notes)
    
    # Estimativa aproximada de tokens: ~1 token para cada 4 caracteres de texto
    total_chars = sum(len(note["content"]) for note in notes)
    estimated_tokens = int(total_chars / 4)
    
    # Preço do Claude Sonnet Input: $3.00 por 1M de tokens
    estimated_cost = (estimated_tokens / 1_000_000.0) * 3.00
    
    return {
        "total_notes": total_notes,
        "estimated_tokens": estimated_tokens,
        "estimated_cost_usd": round(estimated_cost, 4)
    }

async def synthesize_vault_knowledge() -> str:
    """
    Lê todas as notas com source: youtube, consolida o conhecimento e gera uma síntese profunda.
    Salva a síntese no vault em _OYTO/Sintese do Segundo Cerebro.md.
    """
    if synthesis_lock.locked():
        raise RuntimeError("Uma síntese de conhecimento já está em andamento. Por favor, aguarde.")

    async with synthesis_lock:
        notes = get_vault_notes(persona_id=None, is_clone_only=False)
        if not notes:
            raise ValueError("Não há notas do YouTube no vault para sintetizar.")

        # Consolida o contexto do vault
        context_parts = []
        for i, note in enumerate(notes):
            topics = [t for t in note["tags"] if t.startswith("topic/")]
            note_text = (
                f"### VÍDEO {i+1}: {note['title']}\n"
                f"Canal: {note['channel']}\n"
                f"Tópicos: {', '.join(topics)}\n"
                f"Conteúdo:\n{note['content']}\n"
                f"----------------------------------------\n"
            )
            context_parts.append(note_text)

        consolidated_context = "\n".join(context_parts)
        
        system_prompt = (
            "Você é um arquiteto de conhecimento e analista de aprendizado especializado em consolidar insights multidisciplinares.\n"
            "Sua missão é ler o contexto consolidado do vault de vídeos do usuário e gerar uma síntese profunda estruturada."
        )
        
        prompt = (
            "Analise todo o conhecimento acumulado a partir dos vídeos abaixo e crie uma síntese estruturada contendo as seguintes seções:\n\n"
            "1. Resumo Executivo: Resumo geral do conhecimento acumulado (3-5 parágrafos).\n"
            "2. Top 10 Conceitos Recorrentes: Os dez principais tópicos discutidos, acompanhados de uma descrição clara para cada um.\n"
            "3. Frameworks Mentais Identificados: Padrões de raciocínio, estratégias ou regras práticas ensinadas que aparecem em múltiplos vídeos.\n"
            "4. Conexões Não Óbvias: Relações inusitadas ou cruzamentos de ideias entre vídeos de temas aparentemente distantes.\n"
            "5. Lacunas de Conhecimento: Áreas críticas que ainda não estão bem cobertas e sugestões do que estudar ou pesquisar a seguir.\n\n"
            "Aqui está o contexto das notas:\n"
            f"{consolidated_context}\n"
            "Escreva a resposta final no formato Markdown mais rico e polido possível, em português."
        )

        logger.info("Enviando síntese de %d notas ao Claude...", len(notes))
        
        # Executa chamada assíncrona ao LLM com timeout estendido para contextos gigantes
        synthesis_content = await ainvoke_llm(
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt,
            max_tokens=4096,
            temperature=0.3
        )
        
        # Salva o resultado no vault do Obsidian em _OYTO/Sintese do Segundo Cerebro.md
        vault_path = Path(settings.obsidian_vault_path)
        oyto_dir = vault_path / "_OYTO"
        oyto_dir.mkdir(parents=True, exist_ok=True)
        synthesis_file = oyto_dir / "Sintese do Segundo Cerebro.md"
        
        # Cria um frontmatter próprio para a nota de síntese
        now_str = datetime.now().isoformat()
        metadata_header = (
            "---\n"
            "source: oyto_synthesis\n"
            f"generated_at: {now_str}\n"
            f"vault_size: {len(notes)}\n"
            "---\n\n"
        )
        
        synthesis_file.write_text(metadata_header + synthesis_content, encoding="utf-8")
        logger.info("Nota de síntese gravada com sucesso em %s", synthesis_file)
        
        return synthesis_content

def _get_title_overlap(query: str, title: str) -> float:
    import re
    import unicodedata
    
    def normalize(text: str) -> List[str]:
        text = text.lower()
        text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        words = text.split()
        # Filtrar partículas gramaticais muito comuns
        stopwords = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'do', 'da', 'dos', 'das',
            'em', 'no', 'na', 'nos', 'nas', 'para', 'por', 'com', 'sem', 'sob', 'sobre',
            'e', 'ou', 'mas', 'que', 'se', 'como', 'the', 'and', 'or', 'to', 'of', 'in', 'on',
            'at', 'with', 'by', 'for', 'from', 'about', 'an'
        }
        return [w for w in words if len(w) > 2 and w not in stopwords]
        
    query_words = set(normalize(query))
    title_words = set(normalize(title))
    
    if not title_words:
        return 0.0
        
    overlap = title_words.intersection(query_words)
    return len(overlap) / len(title_words)

def perform_rag_search(query: str, notes: List[Dict[str, Any]], top_k: int, min_similarity: float) -> List[Tuple[Dict[str, Any], float]]:
    """
    Calcula similaridade TF-IDF entre a query e as notas do vault.
    Aplica um boost de similaridade se palavras significativas do título da nota estiverem na query.
    Retorna uma lista ordenada de tuplas (nota, score).
    """
    if not notes:
        return []

    # Concatenamos o título e o conteúdo para dar peso ao título
    documents = [f"{note['title']} {note['content']}" for note in notes]
    
    try:
        stopwords = _get_stopwords()
        vectorizer = TfidfVectorizer(stop_words=stopwords, ngram_range=(1, 2), lowercase=True)
        tfidf_matrix = vectorizer.fit_transform(documents)
        query_vec = vectorizer.transform([query])
        
        # Calcula similaridade cosseno
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        results = []
        for idx, note in enumerate(notes):
            base_score = float(similarities[idx])
            
            # Boost por sobreposição de termos do título
            overlap_ratio = _get_title_overlap(query, note['title'])
            if overlap_ratio >= 0.5:
                # Se pelo menos 50% das palavras do título estão na query, eleva o score
                score = max(base_score, overlap_ratio)
            else:
                score = base_score
                
            if score >= min_similarity:
                results.append((note, score))
                
        # Ordena por similaridade decrescente
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    except Exception as e:
        logger.exception("Erro ao executar similaridade TF-IDF no RAG: %s", e)
        return []

async def generate_chat_stream(
    session_id: int,
    user_message: str,
    persona_id: Optional[int] = None,
    is_clone_only: bool = False
) -> AsyncIterator[Dict[str, Any]]:
    """
    Gerador assíncrono para streaming (SSE) de respostas de chat.
    1. Executa RAG para obter notas relevantes.
    2. Constrói o prompt (Neutro vs Persona com Blueprint).
    3. Recupera o histórico de mensagens recentes da sessão.
    4. Chama o Bedrock stream_llm e gera os tokens.
    """
    yield {"event": "search", "data": json.dumps({"status": "searching"})}
    await asyncio.sleep(0.5)  # Pequeno atraso para a UI poder exibir o estado de pesquisa
    
    # 1. Carrega todas as notas de acordo com os filtros
    notes = get_vault_notes(persona_id=persona_id, is_clone_only=is_clone_only)
    
    # 2. Executa a pesquisa semântica TF-IDF
    top_k = settings.brain_retrieval_top_k
    min_sim = settings.brain_retrieval_min_similarity
    
    search_results = perform_rag_search(user_message, notes, top_k, min_sim)
    
    # Constrói blocos de contexto RAG
    rag_context_parts = []
    sources = []
    
    for note, score in search_results:
        # Pega as primeiras 4000 palavras ou o conteúdo completo do markdown
        content_snippet = note["content"][:20000]
        rag_context_parts.append(
            f"--- NOTA: {note['title']} ---\n"
            f"Caminho: {note['relative_path']}\n"
            f"Conteúdo:\n{content_snippet}\n"
            f"-------------------------------\n"
        )
        sources.append({
            "title": note["title"],
            "file_path": note["relative_path"],
            "similarity_score": round(score, 4)
        })
        
    rag_context = "\n".join(rag_context_parts) if rag_context_parts else "Nenhuma nota relevante foi encontrada no vault do usuário."

    # 3. Carrega persona se houver
    system_prompt = ""
    clone_name = None
    
    if persona_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, blueprint FROM clones WHERE id = ?", (persona_id,))
            row = cursor.fetchone()
            if row:
                clone_name = row["name"]
                blueprint = row["blueprint"] or "# Blueprint em processamento..."
                
                system_prompt = (
                    f"Você é um simulador de IA altamente fiel que personifica a mente e a personalidade de {clone_name}.\n"
                    "Seu comportamento, tom, valores e tomadas de decisão são baseados no MODELO MENTAL BLUEPRINT abaixo.\n"
                    "Responda SEMPRE em primeira pessoa ('eu'), incorporando perfeitamente a persona dele(a).\n"
                    "Adote o vocabulário, gírias, ritmo e atitude descritos. Não saia da persona sob nenhuma circunstância.\n"
                    "Quando referenciar uma nota do vault, utilize obrigatoriamente a sintaxe de wikilink [[Nome da Nota]] para criar referências clicáveis.\n"
                    "Responda com base no conhecimento do vault do usuário fornecido abaixo. Se não souber responder com base nisso ou no blueprint, diga com a voz do personagem que não sabe.\n\n"
                    "--- MODELO MENTAL BLUEPRINT ---\n"
                    f"{blueprint}\n\n"
                    "--- CONTEXTO DO VAULT DO USUÁRIO ---\n"
                    f"{rag_context}"
                )
    
    if not system_prompt:
        # Default Oyto Brain neutro
        system_prompt = (
            "Você é o Oyto, o segundo cérebro inteligente do usuário. Suas respostas devem ser baseadas unicamente no conhecimento extraído do vault dele fornecido abaixo.\n"
            "Quando referenciar uma nota do vault, utilize obrigatoriamente a sintaxe de wikilink [[Nome da Nota]] para criar referências clicáveis.\n"
            "Não invente informações que não estejam presentes no contexto do vault. Se não souber a resposta ou se ela não estiver no contexto, diga amigavelmente que não possui essa informação.\n\n"
            "--- CONTEXTO DO VAULT DO USUÁRIO ---\n"
            f"{rag_context}"
        )

    # 4. Recupera histórico de mensagens no banco (limite configurável)
    history_window = settings.brain_chat_history_window
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM brain_chat_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, history_window)
        )
        msg_rows = cursor.fetchall()
        
    messages = []
    for row in msg_rows:
        messages.append({
            "role": row["role"],
            "content": row["content"]
        })
        
    # Adiciona a mensagem atual do usuário
    messages.append({
        "role": "user",
        "content": user_message
    })

    # Envia streaming via Anthropic
    logger.info("Disparando stream do chat para sessão %d via Anthropic...", session_id)
    full_response_text = ""
    
    try:
        async for token in astream_llm(
            messages=messages,
            system=system_prompt
        ):
            full_response_text += token
            yield {"event": "token", "data": json.dumps({"token": token})}
            # Pequeno alívio para o loop de eventos
            await asyncio.sleep(0.001)
            
    except Exception as e:
        logger.exception("Erro crítico durante o streaming da resposta do Claude: %s", e)
        yield {"event": "error", "data": json.dumps({"message": f"Erro na IA: {str(e)}"})}
        return

    # 5. Salva mensagens de chat e fontes no banco SQLite/Postgres
    now_str = datetime.now().isoformat()
    
    # Registra no DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Salva a mensagem do usuário (se ainda não gravada nas etapas de rota)
        cursor.execute(
            "INSERT INTO brain_chat_messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (session_id, user_message, now_str)
        )
        
        # Salva a mensagem do assistente com as fontes em JSON
        sources_json = json.dumps(sources)
        cursor.execute(
            "INSERT INTO brain_chat_messages (session_id, role, content, sources_json, created_at) VALUES (?, 'assistant', ?, ?, ?)",
            (session_id, full_response_text, sources_json, now_str)
        )
        
        # Atualiza o atualizados_em da sessão
        cursor.execute(
            "UPDATE brain_chat_sessions SET updated_at = ? WHERE id = ?",
            (now_str, session_id)
        )
        
        conn.commit()
        assistant_message_id = cursor.lastrowid

    # 6. Dispara geração de título assíncrona se for a primeira mensagem da sessão
    # Uma sessão tem 2 mensagens após a gravação acima (1 user, 1 assistant)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM brain_chat_messages WHERE session_id = ?", (session_id,))
        msg_count = cursor.fetchone()["count"]

    if msg_count <= 2:
        asyncio.create_task(auto_generate_session_title(session_id, user_message))

    # Retorna o evento final 'done' com metadados e fontes
    stats = usage_tracker.get_stats()
    yield {
        "event": "done",
        "data": json.dumps({
            "message_id": assistant_message_id,
            "sources": sources,
            "usage": stats
        })
    }

async def auto_generate_session_title(session_id: int, user_message: str):
    """Gera um título representativo e curto para a sessão de chat em segundo plano."""
    logger.info("Gerando título automático para sessão de chat %d...", session_id)
    try:
        system = "Você é um assistente de organização que gera títulos curtos para chats."
        prompt = (
            "Gere um título curto e expressivo de 3 a 6 palavras em português para um chat que inicia com a seguinte pergunta:\n"
            f"'{user_message}'\n"
            "Responda EXCLUSIVAMENTE com o título limpo, sem aspas, sem pontos finais e sem explicações."
        )
        
        title = await ainvoke_llm(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            max_tokens=30,
            temperature=0.5,
            model=settings.anthropic_model_light
        )
        title = title.strip().strip('"').strip("'")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE brain_chat_sessions SET title = ? WHERE id = ?", (title, session_id))
            conn.commit()
            
        logger.info("Título da sessão %d atualizado para: '%s'", session_id, title)
    except Exception as e:
        logger.error("Falha ao gerar título automático para chat %d: %s", session_id, e)
