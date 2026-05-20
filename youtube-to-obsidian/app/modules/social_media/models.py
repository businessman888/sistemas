from pydantic import BaseModel, Field
from typing import List, Optional

class CreatorCreate(BaseModel):
    username: str = Field(..., description="Nome de usuário do criador sem o @")
    platform: str = Field(..., description="Plataforma do criador (instagram, tiktok ou youtube)")
    category: str = Field(..., description="Categoria/Nicho (ex: Dubai Real Estate)")
    time_window: str = Field(..., description="Janela de histórico (recent, 1_week, 1_month, 3_months)")

class CreatorResponse(BaseModel):
    id: int
    username: str
    platform: str
    category: str
    followers_count: int
    average_views: int
    posts_per_month: int
    time_window: str
    last_scraped: Optional[str] = None
    added_at: str

class ConfigCreate(BaseModel):
    name: str = Field(..., description="Nome descritivo da configuração")
    category: str = Field(..., description="Categoria de criadores a associar (ex: Dubai Real Estate)")
    analysis_instructions: str = Field(..., description="Instruções para análise estrutural dos posts")
    concepts_instructions: str = Field(..., description="Instruções para geração de novos conceitos para o usuário")
    limit_top_k: int = Field(default=3, description="Número de vídeos virais a analisar por criador")

class ConfigResponse(BaseModel):
    id: int
    name: str
    category: str
    analysis_instructions: str
    concepts_instructions: str
    limit_top_k: int
    created_at: str

class PipelineRunRequest(BaseModel):
    config_id: int = Field(..., description="ID da configuração a ser usada")

class PipelineResponse(BaseModel):
    id: int
    config_id: int
    run_date: str
    status: str

class PipelineResultResponse(BaseModel):
    id: int
    pipeline_id: int
    creator_username: str
    video_url: str
    views: int
    platform: str
    caption: Optional[str] = None
    thumbnail: Optional[str] = None
    analysis: Optional[str] = None
    concepts: Optional[str] = None
    created_at: str
