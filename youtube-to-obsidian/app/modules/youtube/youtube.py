"""Valida URLs do YouTube, extrai video_id e busca metadados via yt-dlp."""

import logging
import re

import yt_dlp

from app.models.video import VideoMetadata

logger = logging.getLogger(__name__)

# Padrões aceitos de URL do YouTube
_YOUTUBE_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=(?P<id>[a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?youtu\.be/(?P<id>[a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/(?P<id>[a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/(?P<id>[a-zA-Z0-9_-]{11})"),
]


def extract_video_id(url: str) -> str | None:
    """Extrai o video_id de uma URL do YouTube, ou None se inválida."""
    for pattern in _YOUTUBE_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group("id")
    return None


def validate_youtube_url(url: str) -> str:
    """Valida a URL e retorna o video_id. Levanta ValueError se inválida."""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(
            f"URL inválida: '{url}'. "
            "Formatos aceitos: youtube.com/watch?v=, youtu.be/, youtube.com/shorts/"
        )
    return video_id


def fetch_video_metadata(video_id: str) -> VideoMetadata:
    """Busca metadados do vídeo via yt-dlp sem baixar o vídeo."""
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }

    logger.info("Buscando metadados para video_id=%s", video_id)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "private" in error_msg or "unavailable" in error_msg or "removed" in error_msg:
            raise LookupError("Vídeo não encontrado ou indisponível no YouTube.") from e
        if "sign in" in error_msg:
            raise LookupError("Vídeo requer autenticação (pode ser privado ou com restrição de idade).") from e
        raise ConnectionError(f"Erro ao conectar com o YouTube: {e}") from e

    if not info:
        raise LookupError("Vídeo não encontrado ou indisponível no YouTube.")

    # Monta thumbnail URL com fallback
    thumbnail = info.get("thumbnail", "")
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

    return VideoMetadata(
        video_id=video_id,
        title=info.get("title", "Sem título"),
        channel=info.get("channel", info.get("uploader", "Desconhecido")),
        channel_url=info.get("channel_url", info.get("uploader_url", "")),
        upload_date=info.get("upload_date", ""),
        duration=int(info.get("duration", 0)),
        description=info.get("description", ""),
        thumbnail=thumbnail,
    )
