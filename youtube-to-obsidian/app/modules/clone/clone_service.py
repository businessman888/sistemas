import logging
import re
import asyncio
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
from app.core.anthropic_client import ainvoke_llm

logger = logging.getLogger(__name__)

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
            
            # Se a primeira entrada for do tipo 'playlist', é um canal que retornou as playlists de uploads/shorts.
            # Vamos resolver buscando a playlist de uploads do canal.
            if entries and entries[0].get("_type") == "playlist":
                channel_id = entries[0].get("id")
                if channel_id and channel_id.startswith("UC"):
                    uploads_playlist_id = "UU" + channel_id[2:]
                    uploads_url = f"https://www.youtube.com/playlist?list={uploads_playlist_id}"
                    logger.info("Canal detectado. Buscando playlist de uploads: %s", uploads_url)
                    info = ydl.extract_info(uploads_url, download=False)
                    entries = info.get("entries", []) if info else []
            
            video_ids = []
            for entry in entries:
                if entry and entry.get("id"):
                    # Garante que é um vídeo
                    if entry.get("_type", "url") in ["url", "video"]:
                        video_ids.append(entry["id"])
            return video_ids[:limit]
        except Exception as e:
            logger.error("Erro ao listar videos do canal via yt-dlp: %s", e)
            raise ValueError(f"Não foi possível obter os vídeos do canal: {e}")

# call_anthropic_api removido em favor do anthropic_client centralizado

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

def get_existing_video_ids(clone_name: str) -> set[str]:
    """Varre a pasta local de transcrições do clone e coleta todos os video_ids já processados."""
    vault_path = Path(settings.obsidian_vault_path)
    clone_dir = vault_path / "Brains" / clone_name / "Videos"
    existing_ids = set()
    if not clone_dir.exists():
        return existing_ids
    for file_path in clone_dir.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            for line in content.splitlines()[:15]:
                if "video_id:" in line:
                    vid = line.split("video_id:")[1].strip().strip('"').strip("'")
                    if vid:
                        existing_ids.add(vid)
        except Exception:
            pass
    return existing_ids

def parse_local_video_markdown(file_path: Path) -> Optional[Dict[str, str]]:
    """Carrega o título e o texto de transcrição limpo de um arquivo markdown local do Obsidian."""
    try:
        content = file_path.read_text(encoding="utf-8")
        title = file_path.stem
        if " - " in title:
            title = title.split(" - ", 1)[1]
            
        if "## 📜 Transcrição" in content:
            transcript_part = content.split("## 📜 Transcrição", 1)[1]
            import re
            clean_text = re.sub(r'###\s*\[.*?\]\(.*?\)', '', transcript_part)
            clean_text = "\n".join([line.strip() for line in clean_text.splitlines() if line.strip()])
            return {
                "title": title,
                "text": clean_text
            }
    except Exception as e:
        logger.warning("Erro ao fazer parse local do arquivo %s: %s", file_path, e)
    return None

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
        
        # Carrega IDs de vídeos já transcritos localmente para evitar chamadas de API duplicadas
        existing_ids = get_existing_video_ids(clone_name)
        
        # 3. Transcreve vídeo por vídeo
        for i, video_id in enumerate(video_ids):
            try:
                local_data = None
                if video_id in existing_ids:
                    vault_path = Path(settings.obsidian_vault_path)
                    clone_dir = vault_path / "Brains" / clone_name / "Videos"
                    for file_path in clone_dir.glob("*.md"):
                        try:
                            content = file_path.read_text(encoding="utf-8")
                            if f'video_id: "{video_id}"' in content or f"video_id: '{video_id}'" in content or f"video_id: {video_id}" in content:
                                parsed = parse_local_video_markdown(file_path)
                                if parsed:
                                    local_data = parsed
                                    break
                        except Exception:
                            pass
                
                if local_data:
                    logger.info("[%d/%d] Vídeo ID %s já está transcrito localmente. Pulando transcrição...", i + 1, len(video_ids), video_id)
                    transcripts_data.append(local_data)
                    continue

                logger.info("[%d/%d] Processando vídeo ID: %s via API", i + 1, len(video_ids), video_id)
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
                
        # Se não conseguimos transcrever novos vídeos, mas já temos vídeos salvos localmente, podemos continuar
        if not transcripts_data and not existing_ids:
            raise ValueError("Não foi possível transcrever nenhum dos vídeos do canal e nenhum vídeo antigo foi encontrado no vault local.")
            
        # 4. Gera o Blueprint de Modelo Mental usando a função unificada
        await generate_clone_blueprint(clone_id)
        
    except Exception as e:
        logger.exception("Erro crítico no pipeline de clonagem do clone_id=%d: %s", clone_id, e)
        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clones SET status = 'failed', updated_at = ? WHERE id = ?", (now, clone_id))
            conn.commit()

async def generate_clone_blueprint(clone_id: int) -> str:
    """Gera o Master Mental Model Blueprint do clone e salva no vault usando Bedrock."""
    from app.modules.brain.brain_service import get_vault_notes
    
    # 1. Carrega o Clone
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM clones WHERE id = ?", (clone_id,))
        row = cursor.fetchone()
        
    if not row:
        raise ValueError(f"Clone com id {clone_id} não encontrado no banco")
        
    clone_name = row["name"]
    
    # Atualiza status para analisando
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE clones SET status = 'analyzing' WHERE id = ?", (clone_id,))
        conn.commit()
        
    try:
        # 2. Carrega todas as notas de vídeos associadas a este clone
        notes = get_vault_notes(persona_id=clone_id, is_clone_only=True)
        if not notes:
            raise ValueError(f"Nenhum vídeo importado encontrado no vault para o clone '{clone_name}'")
            
        # Ordena as notas pelo nome do arquivo (que começa com a data YYYY-MM-DD) de forma decrescente (mais recentes primeiro)
        notes.sort(key=lambda x: Path(x["file_path"]).name, reverse=True)
        
        # Limita a no máximo 10 notas mais recentes para a geração do blueprint cognitivo para economizar tokens
        blueprint_notes = notes[:10]
        
        # Concatena os textos das transcrições
        transcripts_text = ""
        for i, note in enumerate(blueprint_notes):
            transcripts_text += f"\nVÍDEO {i+1}: {note['title']}\nCONTEÚDO:\n{note['content']}\n---\n"
            
        system_prompt = (
            "Você é um psicólogo cognitivo e analista comportamental especializado em engenharia reversa de modelos mentais.\n"
            "Sua missão é extrair e detalhar a personalidade, a forma de pensar e a comunicação de um criador de conteúdo a partir de suas falas."
        )
        
        prompt = (
            f"Analise as transcrições do criador de conteúdo '{clone_name}' abaixo e gere um Blueprint cognitivo estruturado contendo exatamente as seguintes seções:\n\n"
            "1. Identidade e voz (tom, vocabulário recorrente, expressões típicas, gírias e ritmo).\n"
            "2. Crenças centrais (o que essa pessoa defende, apoia ou ensina repetidamente).\n"
            "3. Frameworks e metodologias próprias (métodos práticos de tomada de decisão ou ação).\n"
            "4. Conselhos recorrentes (recomendações que aparecem com frequência nos vídeos).\n"
            "5. Anti-padrões (o que essa pessoa critica, rejeita ou orienta a não fazer).\n"
            "6. Exemplos e analogias favoritas (histórias ou analogias que ela costuma usar).\n\n"
            "Aqui estão as transcrições:\n"
            f"{transcripts_text}\n"
            "Responda estruturando as seções em formato Markdown de alta qualidade, em português."
        )
        
        logger.info("Enviando transcrições de %s para geração de Blueprint...", clone_name)
        
        # Executa chamada assíncrona ao LLM
        blueprint_markdown = await ainvoke_llm(
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt,
            max_tokens=4096,
            temperature=0.3
        )
        
        # Salva o arquivo no vault do Obsidian em _OYTO/Clones/Blueprint - {nome_do_clone}.md
        vault_path = Path(settings.obsidian_vault_path)
        clones_dir = vault_path / "_OYTO" / "Clones"
        clones_dir.mkdir(parents=True, exist_ok=True)
        blueprint_file = clones_dir / f"Blueprint - {clone_name}.md"
        
        blueprint_file.write_text(blueprint_markdown, encoding="utf-8")
        logger.info("Blueprint salvo com sucesso em %s", blueprint_file)
        
        # Salva no Banco de Dados e atualiza status para completed
        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE clones SET blueprint = ?, status = 'completed', updated_at = ? WHERE id = ?",
                (blueprint_markdown, now, clone_id)
            )
            conn.commit()
            
        logger.info("Blueprint gerado com sucesso para clone_id=%d (%s)", clone_id, clone_name)
        return blueprint_markdown
        
    except Exception as e:
        logger.exception("Erro ao gerar blueprint para clone_id=%d: %s", clone_id, e)
        now = datetime.now().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clones SET status = 'failed', updated_at = ? WHERE id = ?", (now, clone_id))
            conn.commit()
        raise e

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
    """Carrega o histórico do chat, recupera contexto via TF-IDF e gera resposta do Llama 4 via Bedrock."""
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
    
    # Executa chamada assíncrona
    response_text = await ainvoke_llm(
        messages=history,
        system=system_prompt
    )
    
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
