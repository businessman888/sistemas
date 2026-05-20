from pydantic import BaseModel, Field
from typing import Optional, List

class CloneCreate(BaseModel):
    name: str = Field(..., description="Nome do clone mental")
    channel_url: str = Field(..., description="URL do canal do YouTube")
    max_videos: int = Field(default=10, description="Quantidade máxima de vídeos para transcrever")

class CloneResponse(BaseModel):
    id: int
    name: str
    channel_url: str
    max_videos: int
    status: str
    blueprint: Optional[str] = None
    created_at: str
    updated_at: str

class MessageCreate(BaseModel):
    content: str = Field(..., description="Conteúdo da mensagem enviada pelo usuário")

class MessageResponse(BaseModel):
    id: int
    clone_id: int
    role: str
    content: str
    created_at: str
