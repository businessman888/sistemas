"""Modelos Pydantic v2 para request/response da API de vídeos."""

from datetime import date, datetime
from pydantic import BaseModel, Field


class VideoImportRequest(BaseModel):
    """Payload do POST /api/videos."""

    url: str = Field(..., description="URL do vídeo no YouTube")
    language: str | None = Field(
        default=None,
        description="Idioma preferido para a transcrição (ex: 'pt', 'en')",
    )


class VideoImportResponse(BaseModel):
    """Resposta de sucesso do POST /api/videos."""

    status: str = "imported"
    file_path: str = Field(..., description="Caminho do arquivo .md gerado")
    video_id: str
    title: str
    duration: str
    language_used: str = Field(..., description="Idioma efetivamente usado na transcrição")


class VideoConflictResponse(BaseModel):
    """Resposta quando o vídeo já foi importado (409)."""

    status: str = "already_exists"
    file_path: str
    video_id: str


class VideoListItem(BaseModel):
    """Item na listagem de vídeos importados."""

    title: str
    channel: str
    video_id: str
    url: str
    published_at: date | None = None
    imported_at: datetime | None = None
    duration: str | None = None
    file_path: str
    language: str | None = None


class VideoMetadata(BaseModel):
    """Metadados extraídos do YouTube via yt-dlp."""

    video_id: str
    title: str
    channel: str
    channel_url: str
    upload_date: str  # YYYYMMDD format from yt-dlp
    duration: int  # seconds
    description: str
    thumbnail: str


class TranscriptSegment(BaseModel):
    """Segmento individual da transcrição."""

    text: str
    start: float  # seconds
    duration: float  # seconds


class TranscriptResult(BaseModel):
    """Resultado da busca de transcrição."""

    segments: list[TranscriptSegment]
    language: str


class ErrorResponse(BaseModel):
    """Resposta de erro padronizada."""

    detail: str
