"""Busca transcrição de vídeos do YouTube via youtube-transcript-api."""

import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.models.video import TranscriptResult, TranscriptSegment

logger = logging.getLogger(__name__)

# Instância singleton do cliente da API
_api = YouTubeTranscriptApi()


def fetch_transcript(video_id: str, preferred_language: str = "pt") -> TranscriptResult:
    """Busca transcrição com fallback de idioma.

    Ordem de tentativa:
    1. Idioma preferido (ex: 'pt')
    2. Inglês ('en')
    3. Qualquer idioma disponível
    """
    logger.info(
        "Buscando transcrição para video_id=%s, idioma_preferido=%s",
        video_id,
        preferred_language,
    )

    try:
        transcript_list = _api.list(video_id)
    except TranscriptsDisabled:
        raise ValueError("Este vídeo não possui legendas em nenhum idioma (legendas desabilitadas).")
    except VideoUnavailable:
        raise LookupError("Vídeo não encontrado ou indisponível no YouTube.")
    except Exception as e:
        raise ConnectionError(f"Erro ao conectar com o YouTube para buscar transcrição: {e}") from e

    # Tenta na ordem de preferência
    language_priority = _build_language_priority(preferred_language, transcript_list)

    for lang_code in language_priority:
        try:
            transcript = transcript_list.find_transcript([lang_code])
            fetched = transcript.fetch()

            segments = [
                TranscriptSegment(
                    text=entry.text,
                    start=entry.start,
                    duration=entry.duration,
                )
                for entry in fetched
            ]

            logger.info(
                "Transcrição obtida: idioma=%s, segmentos=%d",
                lang_code,
                len(segments),
            )
            return TranscriptResult(segments=segments, language=lang_code)

        except NoTranscriptFound:
            continue

    # Se nenhum idioma funcionou, tenta tradução automática
    try:
        available = list(transcript_list)
        if available:
            first = available[0]
            # Tenta traduzir para o idioma preferido
            if first.is_translatable:
                translated = first.translate(preferred_language)
                fetched = translated.fetch()
                segments = [
                    TranscriptSegment(
                        text=entry.text,
                        start=entry.start,
                        duration=entry.duration,
                    )
                    for entry in fetched
                ]
                logger.info(
                    "Transcrição traduzida de %s para %s, segmentos=%d",
                    first.language_code,
                    preferred_language,
                    len(segments),
                )
                return TranscriptResult(
                    segments=segments,
                    language=f"{first.language_code}→{preferred_language}",
                )
    except Exception as e:
        logger.warning("Falha ao tentar tradução automática: %s", e)

    raise ValueError("Este vídeo não possui legendas em nenhum idioma disponível.")


def _build_language_priority(
    preferred: str,
    transcript_list: object,
) -> list[str]:
    """Monta lista priorizada de idiomas para tentar."""
    priority = [preferred]

    if preferred != "en":
        priority.append("en")

    # Adiciona todos os idiomas disponíveis que não estão na lista
    try:
        for transcript in transcript_list:
            code = transcript.language_code
            if code not in priority:
                priority.append(code)
    except Exception:
        pass

    return priority
