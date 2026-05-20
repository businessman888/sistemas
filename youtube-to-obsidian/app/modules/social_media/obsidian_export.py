import logging
import frontmatter
from datetime import datetime
from pathlib import Path
from app.core.config import settings
from app.core.utils.slugify import slugify, slugify_tag

logger = logging.getLogger(__name__)

def export_to_obsidian(
    creator_username: str,
    platform: str,
    video_url: str,
    views: int,
    category: str,
    analysis: str,
    concepts: str
) -> str:
    """
    Gera um arquivo Markdown no Obsidian Vault na subpasta 'SocialMedia'
    contendo a análise do vídeo concorrente e os conceitos/roteiros criados.
    Retorna o caminho absoluto do arquivo criado.
    """
    vault_root = Path(settings.obsidian_vault_path)
    output_dir = vault_root / "SocialMedia"
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Erro ao criar diretório SocialMedia no vault: {e}")
        raise OSError(f"Sem permissão ou erro ao acessar pasta do Vault: {output_dir}")
        
    # Montar o nome do arquivo: YYYY-MM-DD - [Plataforma] - [Criador] - Viral Concept.md
    now = datetime.now()
    date_prefix = now.strftime("%Y-%m-%d")
    safe_creator = slugify(creator_username)
    filename = f"{date_prefix} - {platform.upper()} - {safe_creator} - Viral Concept.md"
    file_path = output_dir / filename
    
    # Evitar sobrescrita
    if file_path.exists():
        counter = 1
        while file_path.exists():
            filename = f"{date_prefix} - {platform.upper()} - {safe_creator} - Viral Concept ({counter}).md"
            file_path = output_dir / filename
            counter += 1
            
    # Criar post com frontmatter
    post = frontmatter.Post(
        content="",
        title=f"Roteiro Viral baseado em @{creator_username}",
        creator=creator_username,
        platform=platform,
        video_url=video_url,
        views=views,
        category=category,
        source="social_media",
        status="concept",
        imported_at=now.strftime("%Y-%m-%dT%H:%M:%S"),
        tags=[
            "social-media",
            f"creator/{slugify_tag(creator_username)}",
            f"platform/{platform}",
            f"nicho/{slugify_tag(category)}"
        ]
    )
    
    # Montar corpo do markdown
    content_lines = [
        f"# Roteiro Viral baseado em @{creator_username} ({platform.capitalize()})",
        "",
        "> [!info] Metadados do Post Concorrente",
        f"> - **Criador:** @{creator_username}",
        f"> - **Plataforma:** {platform.capitalize()}",
        f"> - **Métrica (Views):** {views:,}",
        f"> - **Vídeo Referência:** [{video_url}]({video_url})",
        f"> - **Nicho:** {category}",
        "",
        "## 🔍 Análise Estrutural do Post Concorrente",
        analysis,
        "",
        "## 💡 Novos Roteiros & Conceitos Criados",
        concepts,
        "",
        "---",
        f"*Gerado em {now.strftime('%d/%m/%Y')} às {now.strftime('%H:%M')} via Oyto OS*"
    ]
    
    post.content = "\n".join(content_lines) + "\n"
    
    # Salvar
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    logger.info(f"Conceito exportado com sucesso para o vault: {file_path}")
    
    return str(file_path)
