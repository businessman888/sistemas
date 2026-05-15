"""Rotas da API de vídeos: importação e listagem."""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.video import (
    ErrorResponse,
    VideoConflictResponse,
    VideoImportRequest,
    VideoImportResponse,
    VideoListItem,
)
from app.services.obsidian import check_existing_video, list_imported_videos, save_video_markdown
from app.services.transcript import fetch_transcript
from app.services.youtube import fetch_video_metadata, validate_youtube_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post(
    "",
    response_model=VideoImportResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": VideoConflictResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def import_video(request: VideoImportRequest) -> VideoImportResponse:
    """Importa um vídeo do YouTube: extrai metadados, transcrição e salva no vault."""

    # 1. Validar URL e extrair video_id
    try:
        video_id = validate_youtube_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Checar idempotência
    existing_path = check_existing_video(video_id)
    if existing_path:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "already_exists",
                "file_path": existing_path,
                "video_id": video_id,
            },
        )

    # 3. Verificar se o vault existe
    vault_path = settings.youtube_output_dir
    try:
        vault_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise HTTPException(
            status_code=500,
            detail=f"Sem permissão para criar/acessar o diretório: {vault_path}",
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao acessar o diretório do vault: {vault_path} — {e}",
        )

    # 4. Buscar metadados via yt-dlp
    try:
        metadata = fetch_video_metadata(video_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"{e} — tente novamente em alguns instantes.",
        )

    # 5. Buscar transcrição
    language = request.language or settings.default_transcript_language
    try:
        transcript = fetch_transcript(video_id, preferred_language=language)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"{e} — tente novamente em alguns instantes.",
        )

    # 6. Gerar e salvar markdown
    try:
        file_path = save_video_markdown(metadata, transcript)
    except Exception as e:
        logger.exception("Erro ao salvar markdown")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar o arquivo no vault: {e}",
        )

    # 7. Retornar sucesso
    from app.utils.timestamp import seconds_to_timestamp

    return VideoImportResponse(
        status="imported",
        file_path=file_path,
        video_id=video_id,
        title=metadata.title,
        duration=seconds_to_timestamp(metadata.duration),
        language_used=transcript.language,
    )


@router.get("", response_model=list[VideoListItem])
async def list_videos() -> list[VideoListItem]:
    """Lista todos os vídeos já importados no vault."""
    try:
        return list_imported_videos()
    except Exception as e:
        logger.exception("Erro ao listar vídeos importados")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar vídeos: {e}",
        )
