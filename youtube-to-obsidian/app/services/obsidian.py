"""Monta markdown + frontmatter YAML e gerencia arquivos no vault do Obsidian."""

import logging
import re
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.models.video import (
    TranscriptResult,
    VideoListItem,
    VideoMetadata,
)
from app.utils.slugify import slugify, slugify_tag
from app.utils.timestamp import seconds_to_timestamp

logger = logging.getLogger(__name__)


def check_existing_video(video_id: str) -> str | None:
    """Verifica se já existe um arquivo com este video_id no vault.

    Retorna o caminho do arquivo existente ou None.
    """
    output_dir = settings.youtube_output_dir

    if not output_dir.exists():
        return None

    for md_file in output_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            frontmatter = _extract_frontmatter(content)
            if frontmatter.get("video_id") == video_id:
                return str(md_file)
        except Exception as e:
            logger.warning("Erro ao ler %s: %s", md_file, e)
            continue

    return None


def save_video_markdown(
    metadata: VideoMetadata,
    transcript: TranscriptResult,
) -> str:
    """Gera e salva o arquivo markdown no vault do Obsidian.

    Retorna o caminho absoluto do arquivo criado.
    """
    output_dir = settings.youtube_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Monta nome do arquivo: YYYY-MM-DD - Título Slugificado.md
    date_prefix = _format_upload_date(metadata.upload_date)
    safe_title = slugify(metadata.title)
    filename = f"{date_prefix} - {safe_title}.md"
    file_path = output_dir / filename

    # Evita sobrescrita acidental
    if file_path.exists():
        counter = 1
        while file_path.exists():
            filename = f"{date_prefix} - {safe_title} ({counter}).md"
            file_path = output_dir / filename
            counter += 1

    # Gera conteúdo
    now = datetime.now()
    content = _build_markdown(metadata, transcript, now)

    file_path.write_text(content, encoding="utf-8")
    logger.info("Arquivo salvo: %s", file_path)

    return str(file_path)


def list_imported_videos() -> list[VideoListItem]:
    """Lista todos os vídeos importados lendo frontmatter dos arquivos no vault."""
    output_dir = settings.youtube_output_dir

    if not output_dir.exists():
        return []

    videos: list[VideoListItem] = []

    for md_file in sorted(output_dir.glob("*.md"), reverse=True):
        try:
            content = md_file.read_text(encoding="utf-8")
            fm = _extract_frontmatter(content)

            if not fm.get("video_id"):
                continue

            # Parse imported_at
            imported_at = None
            if fm.get("imported_at"):
                try:
                    imported_at = datetime.fromisoformat(str(fm["imported_at"]))
                except (ValueError, TypeError):
                    pass

            # Parse published_at
            published_at = None
            if fm.get("published_at"):
                try:
                    from datetime import date
                    pub_str = str(fm["published_at"])
                    if len(pub_str) == 10:
                        published_at = date.fromisoformat(pub_str)
                except (ValueError, TypeError):
                    pass

            videos.append(
                VideoListItem(
                    title=fm.get("title", "Sem título"),
                    channel=fm.get("channel", "Desconhecido"),
                    video_id=fm["video_id"],
                    url=fm.get("url", ""),
                    published_at=published_at,
                    imported_at=imported_at,
                    duration=fm.get("duration"),
                    file_path=str(md_file),
                    language=fm.get("language"),
                )
            )
        except Exception as e:
            logger.warning("Erro ao processar %s: %s", md_file, e)
            continue

    return videos


def _build_markdown(
    meta: VideoMetadata,
    transcript: TranscriptResult,
    imported_at: datetime,
) -> str:
    """Monta o conteúdo completo do markdown com frontmatter YAML."""
    video_url = f"https://www.youtube.com/watch?v={meta.video_id}"
    duration_str = seconds_to_timestamp(meta.duration)
    date_iso = _format_upload_date(meta.upload_date)
    imported_str = imported_at.strftime("%Y-%m-%dT%H:%M:%S")
    channel_tag = slugify_tag(meta.channel)
    pub_date_br = _format_date_br(meta.upload_date)

    # --- Frontmatter ---
    lines = [
        "---",
        f'title: "{_escape_yaml(meta.title)}"',
        f'channel: "{_escape_yaml(meta.channel)}"',
        f'channel_url: "{meta.channel_url}"',
        f'url: "{video_url}"',
        f'video_id: "{meta.video_id}"',
        f"published_at: {date_iso}",
        f"imported_at: {imported_str}",
        f"duration_seconds: {meta.duration}",
        f'duration: "{duration_str}"',
        f'language: "{transcript.language}"',
        "source: youtube",
        "status: imported",
        "tags:",
        "  - youtube",
        f"  - canal/{channel_tag}",
        "  - source/transcript",
        f'thumbnail: "{meta.thumbnail}"',
        "---",
        "",
        f"# {meta.title}",
        "",
        "> [!info] Metadados",
        f"> - **Canal:** [{meta.channel}]({meta.channel_url})",
        f"> - **Publicado em:** {pub_date_br}",
        f"> - **Duração:** {duration_str}",
        f"> - **URL:** {video_url}",
        "",
        f"![Thumbnail]({meta.thumbnail})",
        "",
        "## 📝 Resumo",
        "*(será preenchido pelo agente de IA ou manualmente)*",
        "",
        "## 🔑 Pontos-Chave",
        "*(será preenchido pelo agente de IA ou manualmente)*",
        "",
        "## 📜 Transcrição",
        "",
    ]

    # --- Transcrição agrupada em blocos de ~30s ---
    transcript_blocks = _group_transcript_blocks(transcript, meta.video_id)
    lines.extend(transcript_blocks)

    # --- Descrição Original ---
    lines.extend([
        "",
        "## 💬 Descrição Original",
    ])
    if meta.description:
        for desc_line in meta.description.split("\n"):
            lines.append(f"> {desc_line}")
    else:
        lines.append("> *(sem descrição)*")

    # --- Notas Pessoais ---
    lines.extend([
        "",
        "## 🗒️ Notas Pessoais",
        "*(espaço livre para anotações manuais)*",
        "",
        "---",
        f"*Importado em {imported_at.strftime('%d/%m/%Y')} às {imported_at.strftime('%H:%M')} via youtube-to-obsidian*",
    ])

    return "\n".join(lines) + "\n"


def _group_transcript_blocks(
    transcript: TranscriptResult,
    video_id: str,
    block_seconds: int = 30,
) -> list[str]:
    """Agrupa segmentos de transcrição em blocos de ~30 segundos."""
    if not transcript.segments:
        return ["*(transcrição vazia)*"]

    lines: list[str] = []
    current_block_start = 0
    current_texts: list[str] = []

    for segment in transcript.segments:
        start_sec = int(segment.start)

        # Se este segmento inicia um novo bloco
        if start_sec >= current_block_start + block_seconds and current_texts:
            # Escreve o bloco acumulado
            ts = seconds_to_timestamp(current_block_start)
            url = f"https://www.youtube.com/watch?v={video_id}&t={current_block_start}s"
            lines.append(f"### [{ts}]({url})")
            lines.append(" ".join(current_texts))
            lines.append("")

            # Alinha o próximo bloco ao múltiplo de block_seconds
            current_block_start = (start_sec // block_seconds) * block_seconds
            current_texts = []

        current_texts.append(segment.text.strip())

    # Último bloco
    if current_texts:
        ts = seconds_to_timestamp(current_block_start)
        url = f"https://www.youtube.com/watch?v={video_id}&t={current_block_start}s"
        lines.append(f"### [{ts}]({url})")
        lines.append(" ".join(current_texts))
        lines.append("")

    return lines


def _extract_frontmatter(content: str) -> dict[str, str]:
    """Extrai pares chave-valor simples do frontmatter YAML."""
    fm: dict[str, str] = {}
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return fm

    for line in match.group(1).split("\n"):
        line = line.strip()
        if ":" not in line or line.startswith("-") or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            fm[key] = value

    return fm


def _format_upload_date(upload_date: str) -> str:
    """Converte YYYYMMDD do yt-dlp para YYYY-MM-DD."""
    if len(upload_date) == 8:
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return upload_date


def _format_date_br(upload_date: str) -> str:
    """Converte YYYYMMDD para DD/MM/YYYY."""
    if len(upload_date) == 8:
        return f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[:4]}"
    return upload_date


def _escape_yaml(text: str) -> str:
    """Escapa caracteres que podem quebrar YAML dentro de aspas duplas."""
    return text.replace("\\", "\\\\").replace('"', '\\"')
