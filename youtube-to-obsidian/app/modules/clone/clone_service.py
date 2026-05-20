import logging
import re
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import yt_dlp
from app.core.config import settings
from app.core.database import get_db_connection
from app.modules.youtube.youtube import fetch_video_metadata
from app.modules.youtube.transcript import fetch_transcript
from app.core.utils.slugify import slugify, slugify_tag
from app.core.utils.timestamp import seconds_to_timestamp

logger = logging.getLogger(__name__)

# Configurações da API Anthropic
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

PT_STOPWORDS = [
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo", "as", "até", "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles", "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em", "entre", "era", "eram", "essa", "essas", "esse", "esses", "esta", "estas", "este", "estes", "eu", "foi", "fomos", "for", "fora", "foram", "forem", "fosse", "fossem", "fui", "há", "haja", "hajam", "houve", "houvemos", "houver", "houvera", "houveram", "houverem", "houvesse", "houvessem", "isso", "isto", "já", "lhe", "lhes", "mais", "mas", "me", "mesmo", "meu", "meus", "minha", "minhas", "muito", "na", "nas", "nem", "no", "nos", "nossa", "nossas", "nosso", "nossos", "num", "numa", "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quando", "que", "quem", "se", "seja", "sejam", "sem", "ser", "será", "serão", "serei", "seria", "seriam", "seu", "seus", "só", "somos", "sou", "sua", "suas", "também", "te", "tem", "têm", "tenha", "tenham", "tenho", "terá", "terão", "terei", "teria", "teriam", "teu", "teus", "tu", "tua", "tuas", "um", "uma", "você", "vocês", "vos"
]

def fetch_channel_videos(channel_url: str, limit: int = 10) -> List[str]:
    """Usa o yt-dlp local para listar os video_ids do canal do YouTube sem fazer download."""
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "playlistend": limit,
    }
    logger.info("Buscando videos do canal: %s (limite: %d)", channel_url, limit)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False)
            if not info:
                return []
            entries = info.get("entries", [])
            video_ids = []
            for entry in entries:
                if entry and entry.get("id"):
                    video_ids.append(entry["id"])
            return video_ids[:limit]
        except Exception as e:
            logger.error("Erro ao listar videos do canal via yt-dlp: %s", e)
            raise ValueError(f"Não foi possível obter os vídeos do canal: {e}")

async def call_anthropic_api(system_prompt: str, messages: List[Dict[str, str]]) -> str:
    """Envia requisição assíncrona para a API da Anthropic Claude."""
    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError("Anthropic API Key não está configurada no arquivo .env")
        
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4096,
        "temperature": 0.7,
        "messages": messages,
        "system": system_prompt
    }
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Falha na API da Anthropic: {response.text}")
            
        res_data = response.json()
        content_list = res_data.get("content", [])
        if not content_list:
            raise Exception("Claude retornou uma resposta vazia.")
            
        return content_list[0].get("text", "").strip()

def _save_clone_video_markdown(clone_name: str, metadata: Any, transcript: Any) -> Path:
    """Gera e salva o arquivo markdown de um vídeo dentro do diretório do clone."""
    vault_path = Path(settings.obsidian_vault_path)
    clone_dir = vault_path / "Brains" / clone_name / "Videos"
    clone_dir.mkdir(parents=True, exist_ok=True)
    
    # Nome do arquivo formatado
    date_prefix = metadata.upload_date
    if len(date_prefix) == 8:
        date_prefix = f"{date_prefix[:4]}-{date_prefix[4:6]}-{date_prefix[6:8]}"
    safe_title = slugify(metadata.title)
    filename = f"{date_prefix} - {safe_title}.md"
    file_path = clone_dir / filename
    
    # Evita sobreposição
    if file_path.exists():
        counter = 1
        while file_path.exists():
            filename = f"{date_prefix} - {safe_title} ({counter}).md"
            file_path = clone_dir / filename
            counter += 1

    # Monta frontmatter e conteúdo do Markdown
    video_url = f"https://www.youtube.com/watch?v={metadata.video_id}"
    duration_str = seconds_to_timestamp(metadata.duration)
    
    lines = [
        "---",
        f'title: "{metadata.title.replace(chr(34), chr(92)+chr(34))}"',
        f'channel: "{metadata.channel.replace(chr(34), chr(92)+chr(34))}"',
        f'url: "{video_url}"',
        f'video_id: "{metadata.video_id}"',
        f"published_at: {date_prefix}",
        f"duration: {duration_str}",
        f"source: mind-clone",
        f"clone_name: {clone_name}",
        "tags:",
        "  - mind-clone",
        f"  - clone/{slugify_tag(clone_name)}",
        "---",
        "",
        f"# {metadata.title}",
        "",
        f"> - **Canal:** [{metadata.channel}]({metadata.channel_url})",
        f"> - **Publicado:** {date_prefix}",
        f"> - **Duração:** {duration_str}",
        f"> - **URL:** {video_url}",
        "",
        "## 📜 Transcrição",
        ""
    ]
    
    # Agrupa segmentos em blocos de 30s
    if not transcript.segments:
        lines.append("*(transcrição vazia)*")
    else:
        current_block_start = 0
        current_texts = []
        for segment in transcript.segments:
            start_sec = int(segment.start)
            if start_sec >= current_block_start + 30 and current_texts:
                ts = seconds_to_timestamp(current_block_start)
                url = f"{video_url}&t={current_block_start}s"
                lines.append(f"### [{ts}]({url})")
                lines.append(" ".join(current_texts))
                lines.append("")
                current_block_start = (start_sec // 30) * 30
                current_texts = []
            current_texts.append(segment.text.strip())
            
        if current_texts:
            ts = seconds_to_timestamp(current_block_start)
            url = f"{video_url}&t={current_block_start}s"
            lines.append(f"### [{ts}]({url})")
            lines.append(" ".join(current_texts))
            lines.append("")
            
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path

async def run_cloning_pipeline(clone_id: int):
    """Executa a transcrição e síntese do modelo mental em background."""
    logger.info("Iniciando pipeline de clonagem para clone_id=%d", clone_id)
    
    # 1. Carrega o Clone
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, channel_url, max_videos FROM clones WHERE id = ?", (clone_id,))
        row = cursor.fetchone()
        
    if not row:
        logger.error("Clone com id %d não encontrado no banco", clone_id)
        return
        
    clone_name, channel_url, max_videos = row["name"], row["channel_url"], row["max_videos"]
    
    try:
        # Atualiza status para transcrevendo
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clones SET status = 'transcribing' WHERE id = ?", (clone_id,))
            conn.commit()
            
        # 2. Busca lista de vídeos via yt-dlp
        video_ids = fetch_channel_videos(channel_url, max_videos)
        if not video_ids:
            raise ValueError("Nenhum vídeo público encontrado neste canal.")
            
        transcripts_data = []
        
        # 3. Transcreve vídeo por vídeo
        for i, video_id in enumerate(video_ids):
            try:
                logger.info("[%d/%d] Processando vídeo ID: %s", i + 1, len(video_ids), video_id)
                metadata = fetch_video_metadata(video_id)
                transcript = fetch_transcript(video_id)
                
                # Salva markdown individual na pasta Brains/Videos do Obsidian
                _save_clone_video_markdown(clone_name, metadata, transcript)
                
                # Concatena o texto completo para processar a inteligência do clone
                full_text = " ".join([seg.text for seg in transcript.segments])
                transcripts_data.append({
                    "title": metadata.title,
                    "text": full_text
                })
            except Exception as e:
                logger.warning("Falha ao transcrever vídeo %s: %s", video_id, e)
                continue
                
        if not transcripts_data:
            raise ValueError("Não foi possível transcrever nenhum dos vídeos do canal.")
            
        # Atualiza status para analisando
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clones SET status = 'analyzing' WHERE id = ?", (clone_id,))
            conn.commit()
            
        # 4. Processamento dos Lotes de Transcrições (Map-Reduce)
        batch_size = 5
        batch_summaries = []
        
        for idx in range(0, len(transcripts_data), batch_size):
            batch = transcripts_data[idx:idx + batch_size]
            logger.info("Processando lote de análise %d a %d de %s", idx + 1, idx + len(batch), clone_name)
            
            # Monta o prompt do lote
            batch_text = ""
            for item in batch:
                batch_text += f"\nTÍTULO: {item['title']}\nCONTEÚDO:\n{item['text']}\n---\n"
                
            system_prompt = (
                "Você é um psicólogo cognitivo e analista comportamental especializado em engenharia reversa de modelos mentais. "
                "Sua missão é extrair a personalidade, tomada de decisões e estilo de comunicação do criador de conteúdo a partir de suas falas."
            )
            
            prompt = (
                "Analise as transcrições de vídeos do criador de conteúdo abaixo. Identifique:\n"
                "1. Filosofia de vida e crenças essenciais (o que ele defende/prega).\n"
                "2. Regras e frameworks práticos que ele aplica para tomar decisões, resolver problemas ou gerir negócios.\n"
                "3. Vocabulário característico, expressões repetitivas, gírias, ritmo e estilo de falar (formal, agressivo, calmo, irônico, etc.).\n"
                "4. Temas mais recorrentes que ele ensina.\n\n"
                f"Aqui está o lote de vídeos:\n{batch_text}\n"
                "Retorne uma análise detalhada em Markdown focando nos pontos acima."
            )
            
            summary = await call_anthropic_api(system_prompt, [{"role": "user", "content": prompt}])
            batch_summaries.append(summary)
            await asyncio.sleep(2) # Evita limite de taxa da API
            
        # 5. Consolidação no Master Blueprint
        logger.info("Consolidando análises no Master Blueprint para %s", clone_name)
        combined_summaries = "\n\n=== ANÁLISE DE LOTE ===\n\n".join(batch_summaries)
        
        sys_prompt_consolidate = (
            "Você é um especialista em psicologia e análise comportamental. Sua tarefa é compilar diferentes fatias de análises "
            "comportamentais sobre um criador de conteúdo e gerar o Master Mental Model Blueprint unificado."
        )
        
        prompt_consolidate = (
            "Abaixo estão resumos de comportamento e estilo do criador de conteúdo obtidos a partir de diferentes lotes de vídeos.\n"
            "Sua tarefa é consolidar essas análises em um único blueprint Markdown completo e muito detalhado.\n\n"
            f"Nome do Criador: {clone_name}\n"
            f"Análises de lotes:\n{combined_summaries}\n\n"
            "Você DEVE retornar exatamente no formato estruturado abaixo (utilize exatamente estes cabeçalhos):\n\n"
            f"# Master Mental Model Blueprint: {clone_name}\n\n"
            "## 1. Filosofia de Vida & Valores Nucleares\n"
            "(Crenças centrais, valores fundamentais e drives motivacionais)\n\n"
            "## 2. Frameworks de Tomada de Decisão\n"
            "(Estratégias práticas, regras mentais e métodos para avaliar riscos e tomar decisões)\n\n"
            "## 3. Estilo de Comunicação & Expressões Comuns\n"
            "(Tom de voz, velocidade, catchphrases, jargões específicos e gírias recorrentes)\n\n"
            "## 4. Conceitos-Chave & Temas Recorrentes\n"
            "(Ideias, teorias ou ferramentas ensinadas com frequência)\n\n"
            "Por favor, seja profundo, evite clichês vazios e escreva em português."
        )
        
        blueprint_markdown = await call_anthropic_api(sys_prompt_consolidate, [{"role": "user", "content": prompt_consolidate}])
        
        # 6. Salva o blueprint no Obsidian
        vault_path = Path(settings.obsidian_vault_path)
        blueprint_file = vault_path / "Brains" / clone_name / f"{clone_name} - Mental Model Blueprint.md"
        blueprint_file.parent.mkdir(parents=True, exist_ok=True)
        blueprint_file.write_text(blueprint_markdown, encoding="utf-8")
        
        # 7. Salva no Banco de Dados SQLite e atualiza status para completed
        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE clones SET blueprint = ?, status = 'completed', updated_at = ? WHERE id = ?",
                (blueprint_markdown, now, clone_id)
            )
            conn.commit()
            
        logger.info("Pipeline de clonagem finalizado com sucesso para clone_id=%d (%s)", clone_id, clone_name)
        
    except Exception as e:
        logger.exception("Erro crítico no pipeline de clonagem do clone_id=%d: %s", clone_id, e)
        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clones SET status = 'failed', updated_at = ? WHERE id = ?", (now, clone_id))
            conn.commit()

def search_local_transcripts(clone_name: str, query: str) -> List[str]:
    """Realiza busca de texto local com TF-IDF em blocos de transcrição salvos na pasta do clone."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
    except ImportError:
        logger.warning("sklearn não instalado. Retornando sem contexto local.")
        return []
        
    vault_path = Path(settings.obsidian_vault_path)
    clone_dir = vault_path / "Brains" / clone_name / "Videos"
    
    if not clone_dir.exists():
        return []
        
    paragraphs = []
    
    for file_path in clone_dir.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            if "## 📜 Transcrição" in content:
                parts = content.split("## 📜 Transcrição", 1)
                transcript_part = parts[1]
                
                # Divide por blocos ### [00:00]
                blocks = transcript_part.split("### [")
                for block in blocks:
                    block = block.strip()
                    if not block:
                        continue
                    # Reconstitui o timestamp
                    paragraphs.append(f"### [{block}")
        except Exception as e:
            logger.warning("Erro ao ler arquivo %s para TF-IDF: %s", file_path, e)
            
    if not paragraphs:
        return []
        
    try:
        vectorizer = TfidfVectorizer(stop_words=PT_STOPWORDS, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(paragraphs)
        query_vec = vectorizer.transform([query])
        
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        top_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.05:  # Limiar mínimo de similaridade
                # Limita a 500 caracteres por bloco para economizar contexto
                results.append(paragraphs[idx][:600])
                if len(results) >= 3:
                    break
        return results
    except Exception as e:
        logger.error("Erro ao rodar TF-IDF do chat: %s", e)
        return []

async def generate_chat_response(clone_id: int, user_message: str) -> str:
    """Carrega o histórico do chat, recupera contexto via TF-IDF e gera resposta do Claude."""
    # 1. Recupera o clone
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, blueprint FROM clones WHERE id = ?", (clone_id,))
        clone_row = cursor.fetchone()
        
    if not clone_row:
        raise ValueError("Clone mental não encontrado.")
        
    clone_name, blueprint = clone_row["name"], clone_row["blueprint"]
    if not blueprint:
        blueprint = "# Blueprint em processamento..."
        
    # 2. Busca RAG local nas transcrições
    rag_blocks = search_local_transcripts(clone_name, user_message)
    rag_context = ""
    if rag_blocks:
        rag_context = "\n--- CONTEXTO DE VÍDEOS ENCONTRADO ---\n" + "\n\n".join(rag_blocks) + "\n-------------------------------------\n"
        
    # 3. Carrega o histórico de mensagens recentes (últimas 10)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM clone_messages WHERE clone_id = ? ORDER BY id ASC LIMIT 10",
            (clone_id,)
        )
        rows = cursor.fetchall()
        
    history = []
    for row in rows:
        history.append({
            "role": "user" if row["role"] == "user" else "assistant",
            "content": row["content"]
        })
        
    # Adiciona a mensagem atual
    history.append({
        "role": "user",
        "content": user_message
    })
    
    # 4. Constrói o System Prompt e chama o Claude
    system_prompt = (
        f"Você é um simulador de IA altamente fiel que personifica a mente e a personalidade de {clone_name}.\n"
        "Seu comportamento, tom, valores e tomadas de decisão são baseados no MODELO MENTAL BLUEPRINT abaixo.\n"
        "Responda SEMPRE em primeira pessoa ('eu'), incorporando perfeitamente a persona dele(a).\n"
        "Adote o vocabulário, gírias, ritmo e atitude descritos. Não saia da persona sob nenhuma circunstância.\n"
        "Caso o contexto RAG abaixo seja fornecido, use-o para responder à pergunta de forma ainda mais precisa, referindo-se a ele como 'o que eu já falei no meu vídeo'.\n\n"
        "--- MODELO MENTAL BLUEPRINT ---\n"
        f"{blueprint}\n\n"
        f"{rag_context}"
    )
    
    response_text = await call_anthropic_api(system_prompt, history)
    
    # 5. Salva mensagens no banco de dados
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Salva a mensagem do usuário
        cursor.execute(
            "INSERT INTO clone_messages (clone_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (clone_id, user_message, now)
        )
        # Salva a resposta da IA
        cursor.execute(
            "INSERT INTO clone_messages (clone_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
            (clone_id, response_text, now)
        )
        conn.commit()
        
    return response_text
