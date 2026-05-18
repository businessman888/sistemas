import logging
import re
from pathlib import Path
import frontmatter

from app.core.config import settings
from app.core.similarity import calculate_similarities, extract_keywords

logger = logging.getLogger(__name__)

def update_vault_graph():
    """
    Varre o vault procurando notas com 'source: youtube'.
    Calcula similaridade e tags para elas e atualiza os arquivos.
    """
    output_dir = Path(settings.obsidian_vault_path)
    if not output_dir.exists():
        logger.warning(f"Vault path {output_dir} does not exist.")
        return
        
    youtube_notes = []
    
    # Busca todas as notas .md
    # Como o usuário pode ter outras pastas, vamos varrer o vault inteiro.
    # Mas para performance vamos varrer recursivamente.
    for md_file in output_dir.rglob("*.md"):
        try:
            post = frontmatter.load(md_file)
            if post.metadata.get("source") == "youtube":
                youtube_notes.append(md_file)
        except Exception:
            continue
            
    if len(youtube_notes) < 2:
        logger.info("Menos de 2 notas do youtube encontradas. Apenas atualizando tags.")
        for md_file in youtube_notes:
            _update_single_note_tags(md_file)
        return
        
    documents = {}
    posts = {}
    
    for md_file in youtube_notes:
        try:
            post = frontmatter.load(md_file)
            posts[str(md_file)] = post
            # O texto para similaridade será a transcrição (content) + title + description
            text = str(post.metadata.get("title", "")) + " " + post.content
            documents[str(md_file)] = text
        except Exception as e:
            logger.warning(f"Erro ao ler {md_file}: {e}")
            
    # Calcular similaridades
    similarities = calculate_similarities(documents, settings.related_min_similarity)
    
    # Atualizar as notas
    connections_created = 0
    notes_processed = 0
    
    for file_path_str, post in posts.items():
        changed = False
        md_file = Path(file_path_str)
        text = documents[file_path_str]
        
        # 1. Tags
        existing_tags = post.metadata.get("tags", [])
        if not isinstance(existing_tags, list):
            existing_tags = [existing_tags] if existing_tags else []
            
        topic_tags = [t for t in existing_tags if str(t).startswith("topic/")]
        if not topic_tags:
            keywords = extract_keywords(text, settings.topic_tags_count)
            for kw in keywords:
                tag = f"topic/{kw}"
                if tag not in existing_tags:
                    existing_tags.append(tag)
                    changed = True
            if changed:
                post.metadata["tags"] = existing_tags
                
        # 2. Relacionados
        related_scores = similarities.get(file_path_str, [])
        top_related = related_scores[:settings.related_videos_count]
        
        # Atualizar a seção Relacionados no content
        new_content, rel_changed = _update_related_section(post.content, top_related)
        if rel_changed:
            post.content = new_content
            changed = True
            connections_created += len(top_related)
            
        if changed:
            try:
                md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
                notes_processed += 1
            except Exception as e:
                logger.error(f"Erro ao salvar {md_file}: {e}")
                
    logger.info(f"Grafo atualizado: {notes_processed} notas modificadas, {connections_created} conexões (links) escritas.")
    return notes_processed, connections_created

def _update_single_note_tags(md_file: Path):
    try:
        post = frontmatter.load(md_file)
        text = str(post.metadata.get("title", "")) + " " + post.content
        existing_tags = post.metadata.get("tags", [])
        if not isinstance(existing_tags, list):
            existing_tags = [existing_tags] if existing_tags else []
            
        topic_tags = [t for t in existing_tags if str(t).startswith("topic/")]
        if not topic_tags:
            keywords = extract_keywords(text, settings.topic_tags_count)
            changed = False
            for kw in keywords:
                tag = f"topic/{kw}"
                if tag not in existing_tags:
                    existing_tags.append(tag)
                    changed = True
            if changed:
                post.metadata["tags"] = existing_tags
                md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Erro ao atualizar tags unitárias {md_file}: {e}")

def _update_related_section(content: str, related: list) -> tuple[str, bool]:
    """
    Atualiza ou insere a seção '## 🔗 Relacionados'.
    Retorna o novo conteúdo e um bool indicando se houve mudança.
    """
    heading = "## 🔗 Relacionados"
    
    # Criar bloco de texto dos novos relacionados
    if not related:
        new_block = f"{heading}\n*(Nenhum vídeo similar encontrado ainda)*\n"
    else:
        lines = [heading]
        for related_file_str, score in related:
            related_file = Path(related_file_str)
            # O nome do arquivo sem extensão
            note_name = related_file.stem
            lines.append(f"- [[{note_name}]]")
        lines.append("")
        new_block = "\n".join(lines)
        
    # Regex para encontrar a seção atual de relacionados até o próximo ## 
    pattern = r"## 🔗 Relacionados\n.*?(?=\n## |\Z)"
    
    if "## 🔗 Relacionados" in content:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            old_block = match.group(0)
            if old_block.strip() == new_block.strip():
                return content, False
            new_content = content[:match.start()] + new_block.strip() + "\n" + content[match.end():]
            return new_content, True
    
    # Se não existe, vamos inserir antes de "## 📝 Resumo" ou "## 📜 Transcrição"
    insert_before = ["## 📝 Resumo", "## 📜 Transcrição", "## 🗒️ Notas Pessoais"]
    for target in insert_before:
        if target in content:
            idx = content.index(target)
            new_content = content[:idx] + new_block + "\n" + content[idx:]
            return new_content, True
            
    # Fallback, adiciona no final
    return content + "\n\n" + new_block, True
